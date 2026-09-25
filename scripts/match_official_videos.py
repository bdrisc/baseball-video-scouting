#!/usr/bin/env python3
"""Match local Statcast pitches to official Baseball Savant pitch pages.

One MLB game feed is fetched per game. No video media is downloaded.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
import time
import urllib.error
import urllib.request
from collections import Counter
from datetime import date
from pathlib import Path
from typing import Callable
from uuid import UUID

REPORT_FIELDS = (
    "pitch_id",
    "game_date",
    "game_pk",
    "pitcher",
    "batter",
    "status",
    "reason",
    "play_id",
    "video_url",
    "video_level",
    "video_notes",
)
LINK_FIELDS = (
    "pitch_id",
    "game_pk",
    "pitcher",
    "batter",
    "video_url",
    "video_level",
    "video_notes",
)
REQUIRED = {"game_date", "game_pk", "at_bat_number", "pitch_number", "pitcher", "batter"}
FEED_URL = "https://statsapi.mlb.com/api/v1.1/game/{game_pk}/feed/live"
VIDEO_URL = "https://baseballsavant.mlb.com/sporty-videos?playId={play_id}"


class MatchError(ValueError):
    """Input or game-feed data cannot be trusted for automatic matching."""


def positive_int(value: object) -> int:
    """Parse numeric IDs from CSV or MLB JSON without truncation."""
    if isinstance(value, bool):
        raise ValueError("boolean is not an ID")
    result = int(str(value))
    if result < 1 or str(result) != str(value).strip():
        raise ValueError("invalid positive integer")
    return result


def pitch_rows(paths: list[Path], start: date, end: date) -> dict[int, list[dict[str, str]]]:
    """Read source rows in date range and reject conflicting keys."""
    games: dict[int, list[dict[str, str]]] = {}
    seen: dict[str, tuple[int, int, int, int, int, str, str, str]] = {}
    for path in paths:
        with path.open(encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            missing = REQUIRED - set(reader.fieldnames or [])
            if missing:
                raise MatchError(f"{path.name}: missing columns {', '.join(sorted(missing))}")
            for line, row in enumerate(reader, start=2):
                try:
                    day = date.fromisoformat(row["game_date"])
                    if not start <= day <= end:
                        continue
                    game = positive_int(row["game_pk"])
                    at_bat = positive_int(row["at_bat_number"])
                    pitch = positive_int(row["pitch_number"])
                    pitcher = positive_int(row["pitcher"])
                    batter = positive_int(row["batter"])
                except (TypeError, ValueError) as exc:
                    raise MatchError(f"{path.name}:{line}: invalid pitch identity") from exc
                key = f"{game}_{at_bat}_{pitch}"
                inning = (row.get("inning") or "").strip()
                half = (row.get("inning_topbot") or "").strip()
                identity = (game, at_bat, pitch, pitcher, batter, day.isoformat(), inning, half)
                if key in seen:
                    if seen[key] != identity:
                        raise MatchError(f"Conflicting source rows for {key}")
                    continue
                seen[key] = identity
                games.setdefault(game, []).append(
                    {
                        "pitch_id": key,
                        "game_date": day.isoformat(),
                        "game_pk": str(game),
                        "at_bat_number": str(at_bat),
                        "pitch_number": str(pitch),
                        "pitcher": str(pitcher),
                        "batter": str(batter),
                        "inning": inning,
                        "inning_topbot": half,
                    }
                )
    return games


def fetch_game(game_pk: int, cache_dir: Path, *, refresh: bool = False) -> dict:
    """Cache the official JSON game feed for reproducible reruns."""
    path = cache_dir / f"{game_pk}.json"
    if path.exists() and not refresh:
        cached = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(cached, dict):
            raise MatchError(f"Game {game_pk} has an invalid cached feed")
        return cached
    request = urllib.request.Request(
        FEED_URL.format(game_pk=game_pk),
        headers={
            "User-Agent": "baseball-video-scouting/1.0 (personal research)",
            "Accept": "application/json",
        },
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        data = json.load(response)
    if not isinstance(data, dict) or not isinstance(
        data.get("liveData", {}).get("plays", {}).get("allPlays"), list
    ):
        raise MatchError(f"Game {game_pk} did not return a valid MLB play feed")
    cache_dir.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".json.part")
    try:
        temporary.write_text(json.dumps(data), encoding="utf-8")
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)
    return data


def index_feed(feed: dict) -> dict[tuple[int, int], list[tuple[dict, dict]]]:
    """Index only actual pitches by one-based at-bat and pitch number."""
    index: dict[tuple[int, int], list[tuple[dict, dict]]] = {}
    for play in feed.get("liveData", {}).get("plays", {}).get("allPlays", []):
        try:
            at_bat = int(play["about"]["atBatIndex"]) + 1
        except (KeyError, ValueError, TypeError):
            continue
        for event in play.get("playEvents", []):
            if event.get("isPitch") is not True:
                continue
            try:
                pitch_number = positive_int(event["pitchNumber"])
            except (KeyError, ValueError, TypeError):
                continue
            index.setdefault((at_bat, pitch_number), []).append((play, event))
    return index


def match_pitch(row: dict[str, str], index: dict) -> dict[str, str]:
    """Fail closed when identities disagree or the video ID is absent."""
    result = {field: row.get(field, "") for field in REPORT_FIELDS}
    result.update(
        status="review", reason="", play_id="", video_url="", video_level="", video_notes=""
    )
    candidates = index.get((int(row["at_bat_number"]), int(row["pitch_number"])), [])
    if len(candidates) != 1:
        result["reason"] = "no_pitch_event" if not candidates else "ambiguous_pitch_event"
        return result
    play, event = candidates[0]
    try:
        if positive_int(play["matchup"]["pitcher"]["id"]) != int(row["pitcher"]) or positive_int(
            play["matchup"]["batter"]["id"]
        ) != int(row["batter"]):
            result["reason"] = "player_id_mismatch"
            return result
        if row.get("inning") and positive_int(play["about"]["inning"]) != int(row["inning"]):
            result["reason"] = "inning_mismatch"
            return result
    except (KeyError, ValueError, TypeError):
        result["reason"] = "missing_game_identity"
        return result
    half = str(play["about"].get("halfInning", "")).lower()
    source_half = str(row.get("inning_topbot", "")).lower()
    if source_half and half != {"bot": "bottom"}.get(source_half, source_half):
        result["reason"] = "inning_half_mismatch"
        return result
    try:
        play_id = str(UUID(str(event["playId"])))
    except (KeyError, ValueError, TypeError):
        result["reason"] = "missing_play_id"
        return result
    result.update(
        status="matched",
        reason="",
        play_id=play_id,
        video_url=VIDEO_URL.format(play_id=play_id),
        video_level="Pitch",
        video_notes="Official Baseball Savant pitch page; matched to MLB game feed",
    )
    return result


def write_csv(path: Path, fields: tuple[str, ...], rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".part")
    try:
        with temporary.open("w", encoding="utf-8", newline="") as output:
            writer = csv.DictWriter(output, fieldnames=fields, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(rows)
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def run(
    input_dir: Path,
    start: date,
    end: date,
    output_dir: Path,
    cache_dir: Path,
    *,
    pattern: str = "statcast_*.csv",
    refresh: bool = False,
    delay: float = 1.0,
    fetcher: Callable[..., dict] = fetch_game,
) -> Counter:
    if start > end or delay < 0:
        raise MatchError("Date range or delay is invalid")
    paths = sorted(input_dir.glob(pattern))
    if not paths:
        raise MatchError(f"No files matched {pattern!r} in {input_dir}")
    games = pitch_rows(paths, start, end)
    if not games:
        raise MatchError("No pitches in the requested date range")
    report: list[dict[str, str]] = []
    for index, (game, pitches) in enumerate(sorted(games.items())):
        if index and delay:
            time.sleep(delay)
        try:
            feed = fetcher(game, cache_dir, refresh=refresh)
            if positive_int(feed["gamePk"]) != game:
                raise MatchError("MLB feed game ID differs from source")
            feed_date = feed["gameData"]["datetime"]["originalDate"]
            if any(row["game_date"] != feed_date for row in pitches):
                raise MatchError("MLB feed date differs from source")
            events = index_feed(feed)
            report.extend(match_pitch(row, events) for row in pitches)
        except (OSError, ValueError, TypeError, KeyError, urllib.error.URLError) as exc:
            report.extend(
                {
                    **{field: row.get(field, "") for field in REPORT_FIELDS},
                    "status": "review",
                    "reason": f"game_feed_error:{type(exc).__name__}",
                }
                for row in pitches
            )
    report.sort(key=lambda row: (row["game_date"], row["pitch_id"]))
    play_ids = Counter(row["play_id"] for row in report if row["status"] == "matched")
    for row in report:
        if row["play_id"] and play_ids[row["play_id"]] > 1:
            row.update(status="review", reason="duplicate_play_id", video_url="")
    write_csv(output_dir / "video_match_report.csv", REPORT_FIELDS, report)
    write_csv(
        output_dir / "video_links_matched.csv",
        LINK_FIELDS,
        [row for row in report if row["status"] == "matched"],
    )
    return Counter(row["reason"] or "matched" for row in report)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-dir", type=Path, default=Path("data/raw/statcast/2026"))
    parser.add_argument("--start-date", type=date.fromisoformat, required=True)
    parser.add_argument("--end-date", type=date.fromisoformat, required=True)
    parser.add_argument(
        "--output-dir", type=Path, help="Output directory (defaults to a date-specific folder)"
    )
    parser.add_argument("--cache-dir", type=Path, default=Path("data/raw/mlb_game_feeds"))
    parser.add_argument("--pattern", default="statcast_*.csv")
    parser.add_argument("--refresh", action="store_true")
    parser.add_argument("--delay", type=float, default=1.0)
    args = parser.parse_args()
    output_dir = args.output_dir or Path("data/processed/video_matches") / (
        f"{args.start_date.isoformat()}_{args.end_date.isoformat()}"
    )
    try:
        summary = run(
            args.input_dir,
            args.start_date,
            args.end_date,
            output_dir,
            args.cache_dir,
            pattern=args.pattern,
            refresh=args.refresh,
            delay=args.delay,
        )
    except (MatchError, OSError) as exc:
        print(f"Video matching stopped: {exc}", file=sys.stderr)
        return 1
    for label, count in sorted(summary.items()):
        print(f"{label}: {count:,}")
    print(f"Report: {output_dir / 'video_match_report.csv'}")
    print(f"Matched links: {output_dir / 'video_links_matched.csv'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
