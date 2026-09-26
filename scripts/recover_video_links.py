#!/usr/bin/env python3
"""Retry reviewed video matches against MLB feeds without guessing pitch identities.

Only previously reviewed rows are retried. Recovered exact matches can be
passed to apply_video_links after inspection; possible nearby events are
listed for manual review and are never exported as importable links.
"""

from __future__ import annotations

import argparse
import csv
import sys
import time
from collections import Counter
from datetime import date
from pathlib import Path
from typing import Callable
from uuid import UUID

from scripts.match_official_videos import (
    LINK_FIELDS,
    VIDEO_URL,
    MatchError,
    fetch_game,
    index_feed,
    match_pitch,
    pitch_rows,
    positive_int,
    write_csv,
)

REVIEW_FIELDS = (
    "pitch_id", "game_date", "game_pk", "pitcher", "batter",
    "previous_reason", "current_reason", "possible_same_at_bat_urls",
)


def read_report(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        required = {"pitch_id", "game_date", "game_pk", "pitcher", "batter", "status", "reason", "play_id"}
        if required - set(reader.fieldnames or []):
            raise MatchError("Review report lacks pitch/game/player/status fields")
        rows = list(reader)
    if len({row["pitch_id"] for row in rows}) != len(rows):
        raise MatchError("Duplicate pitch IDs in review report")
    return rows


def possible_events(row: dict[str, str], feed: dict) -> str:
    """Show nearby events with matching players, never treat them as confirmed."""
    urls: list[str] = []
    for play in feed.get("liveData", {}).get("plays", {}).get("allPlays", []):
        try:
            if int(play["about"]["atBatIndex"]) + 1 != int(row["at_bat_number"]):
                continue
            if positive_int(play["matchup"]["pitcher"]["id"]) != int(row["pitcher"]):
                continue
            if positive_int(play["matchup"]["batter"]["id"]) != int(row["batter"]):
                continue
        except (KeyError, ValueError, TypeError):
            continue
        for event in play.get("playEvents", []):
            if event.get("isPitch") is not True:
                continue
            try:
                url = VIDEO_URL.format(play_id=str(UUID(str(event["playId"]))))
            except (KeyError, ValueError, TypeError):
                continue
            if url not in urls:
                urls.append(url)
    return " | ".join(urls[:5])


def recover(
    report_path: Path,
    input_dir: Path,
    cache_dir: Path,
    output_dir: Path,
    *,
    refresh: bool = False,
    delay: float = 1.0,
    fetcher: Callable[..., dict] = fetch_game,
) -> Counter[str]:
    if delay < 0:
        raise MatchError("Delay cannot be negative")
    report = read_report(report_path)
    pending = [row for row in report if row["status"] == "review"]
    if not pending:
        raise MatchError("No review rows in report")
    days = sorted({date.fromisoformat(row["game_date"]) for row in pending})
    paths = [input_dir / f"statcast_{day}.csv" for day in days]
    missing = [path for path in paths if not path.is_file()]
    if missing:
        raise MatchError(f"Missing raw Statcast file: {missing[0]}")
    source = pitch_rows(paths, days[0], days[-1])
    source_by_id = {row["pitch_id"]: row for rows in source.values() for row in rows}
    for row in pending:
        original = source_by_id.get(row["pitch_id"])
        if original is None or any(original[name] != row[name] for name in (
            "game_date", "game_pk", "pitcher", "batter"
        )):
            raise MatchError(f"Source identity differs for {row['pitch_id']}")
    used_play_ids = {row["play_id"] for row in report if row["status"] == "matched" and row["play_id"]}
    by_game: dict[int, list[dict[str, str]]] = {}
    for row in pending:
        by_game.setdefault(int(row["game_pk"]), []).append(row)
    proposed: list[dict[str, str]] = []
    unresolved: list[dict[str, str]] = []
    counts: Counter[str] = Counter()
    for number, (game, rows) in enumerate(sorted(by_game.items())):
        if number and delay:
            time.sleep(delay)
        try:
            feed = fetcher(game, cache_dir, refresh=refresh)
            if positive_int(feed["gamePk"]) != game or any(
                feed["gameData"]["datetime"]["originalDate"] != row["game_date"]
                for row in rows
            ):
                raise MatchError("Feed game/date differs from source")
            index = index_feed(feed)
        except (OSError, ValueError, TypeError, KeyError) as exc:
            for row in rows:
                unresolved.append({**row, "previous_reason": row["reason"],
                                   "current_reason": f"game_feed_error:{type(exc).__name__}",
                                   "possible_same_at_bat_urls": ""})
                counts["feed_error"] += 1
            continue
        for row in rows:
            source_row = source_by_id[row["pitch_id"]]
            result = match_pitch(source_row, index)
            play_id = result["play_id"]
            if result["status"] == "matched" and play_id in used_play_ids:
                result.update(status="review", reason="play_id_already_matched")
            if result["status"] == "matched":
                used_play_ids.add(play_id)
                proposed.append(result)
                counts["recovered"] += 1
            else:
                unresolved.append({**row, "previous_reason": row["reason"],
                                   "current_reason": result["reason"],
                                   "possible_same_at_bat_urls": possible_events(source_row, feed)})
                counts[f"review:{result['reason']}"] += 1
    write_csv(output_dir / "recovered_links.csv", LINK_FIELDS, proposed)
    write_csv(output_dir / "still_needs_review.csv", REVIEW_FIELDS, unresolved)
    return counts


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", required=True, type=Path)
    parser.add_argument("--input-dir", type=Path, default=Path("data/raw/statcast/2026"))
    parser.add_argument("--cache-dir", type=Path, default=Path("data/raw/mlb_game_feeds"))
    parser.add_argument("--output-dir", type=Path, help="Default: sibling recovery folder")
    parser.add_argument("--refresh", action="store_true", help="Refetch MLB feeds for reviewed games")
    parser.add_argument("--delay", type=float, default=1.0)
    args = parser.parse_args()
    output_dir = args.output_dir or args.report.parent / "recovery"
    try:
        counts = recover(args.report, args.input_dir, args.cache_dir, output_dir,
                         refresh=args.refresh, delay=args.delay)
    except (MatchError, OSError, ValueError) as exc:
        print(f"Recovery stopped: {exc}", file=sys.stderr)
        return 1
    for reason, count in sorted(counts.items()):
        print(f"{reason}: {count:,}")
    print(f"Exact links to inspect: {output_dir / 'recovered_links.csv'}")
    print(f"Unresolved manual review: {output_dir / 'still_needs_review.csv'}")
    print("No database changes were made.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
