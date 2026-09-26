#!/usr/bin/env python3
"""Read-only season audit: source coverage, link identities, and API query times."""

from __future__ import annotations

import argparse
import csv
import os
import random
import statistics
import sys
import time
from collections import Counter
from datetime import date
from pathlib import Path
from urllib.parse import urlparse

import psycopg
from psycopg.rows import dict_row

# Call the actual route handlers against the private database. API Gateway,
# Cognito, and browser network time are outside these measurements.
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
from app.routers.catalog import list_seasons, list_teams  # noqa: E402
from app.routers.pitchers import list_pitcher_games, search_pitchers  # noqa: E402
from app.routers.pitches import pitch_aggregates, search_pitches  # noqa: E402
from app.schemas.filters import (  # noqa: E402
    PitchAggregateFilters,
    PitcherSearchFilters,
    PitchFilters,
)


class AuditError(ValueError):
    """Source, target database, or report does not match the requested audit."""


def load_report(path: Path, start: date, end: date) -> tuple[Counter[str], list[dict[str, str]]]:
    """Validate a match report and retain matched rows for independent DB checks."""
    if not path.is_file():
        raise AuditError(f"Missing report: {path}")
    counts: Counter[str] = Counter()
    matches: list[dict[str, str]] = []
    seen: set[str] = set()
    with path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        required = {
            "pitch_id",
            "game_date",
            "game_pk",
            "pitcher",
            "batter",
            "status",
            "reason",
            "video_url",
        }
        if required - set(reader.fieldnames or []):
            raise AuditError(f"Missing columns in {path}")
        for row in reader:
            pitch_id = row["pitch_id"]
            if pitch_id in seen or not start <= date.fromisoformat(row["game_date"]) <= end:
                raise AuditError(f"Duplicate pitch or date outside the range in {path}")
            seen.add(pitch_id)
            if row["status"] == "matched":
                parsed = urlparse(row["video_url"])
                if (parsed.scheme, parsed.netloc, parsed.path) != (
                    "https",
                    "baseballsavant.mlb.com",
                    "/sporty-videos",
                ):
                    raise AuditError(f"Unexpected video URL in {path}")
                matches.append(row)
                counts["matched"] += 1
            elif row["status"] == "review":
                counts[f"review:{row['reason']}"] += 1
            else:
                raise AuditError(f"Unexpected match status in {path}")
    return counts, matches


def audit_reports(
    connection: psycopg.Connection,
    report_root: Path,
    ranges: list[tuple[date, date]],
    sample_size: int,
) -> int:
    """Reconcile every pitch and compare a reproducible link sample to the DB."""
    print("\nMonth                 Pitches  Linked  Matched  Review  Coverage")
    print("-----------------------------------------------------------------")
    reviews: Counter[str] = Counter()
    samples: list[dict[str, str]] = []
    for start, end in ranges:
        path = report_root / f"{start}_{end}" / "video_match_report.csv"
        counts, matches = load_report(path, start, end)
        source_count = sum(counts.values())
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT COUNT(*) AS pitches,
                       COUNT(v.pitch_id) FILTER (WHERE v.video_available IS TRUE) AS linked
                FROM pitches p JOIN games g ON g.game_pk = p.game_pk
                LEFT JOIN videos v ON v.pitch_id = p.pitch_id
                WHERE g.game_date BETWEEN %s AND %s
                """,
                (start, end),
            )
            totals = cursor.fetchone()
        if totals["pitches"] != source_count:
            raise AuditError(
                f"{start}–{end}: report has {source_count} rows, database has {totals['pitches']}"
            )
        if totals["linked"] < counts["matched"]:
            raise AuditError(f"{start}–{end}: fewer linked pitches than source matches")
        review_count = source_count - counts["matched"]
        reviews.update({key: value for key, value in counts.items() if key.startswith("review:")})
        print(
            f"{start}–{end}  {source_count:7,}  {totals['linked']:6,}  "
            f"{counts['matched']:7,}  {review_count:6,}  "
            f"{100 * totals['linked'] / source_count:.2f}%"
        )
        samples.extend(
            random.Random(start.isoformat()).sample(matches, min(sample_size, len(matches)))
        )

    print("\nReview reasons:")
    for reason, count in sorted(reviews.items()):
        print(f"  {reason.removeprefix('review:')}: {count:,}")

    ids = [row["pitch_id"] for row in samples]
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT p.pitch_id, p.game_pk, g.game_date, pitcher.mlb_id AS pitcher,
                   batter.mlb_id AS batter, v.video_url, v.video_available
            FROM pitches p JOIN games g ON g.game_pk = p.game_pk
            JOIN players pitcher ON pitcher.player_id = p.pitcher_id
            JOIN players batter ON batter.player_id = p.batter_id
            LEFT JOIN videos v ON v.pitch_id = p.pitch_id
            WHERE p.pitch_id = ANY(%s)
            """,
            (ids,),
        )
        found = {row["pitch_id"]: row for row in cursor.fetchall()}
    if len(found) != len(samples):
        raise AuditError("Some sampled pitches are absent from the database")
    preserved = []
    for row in samples:
        actual = found[row["pitch_id"]]
        if (
            actual["game_pk"],
            actual["game_date"],
            actual["pitcher"],
            actual["batter"],
            actual["video_available"],
        ) != (
            int(row["game_pk"]),
            date.fromisoformat(row["game_date"]),
            int(row["pitcher"]),
            int(row["batter"]),
            True,
        ):
            raise AuditError(f"Sampled pitch differs from its report: {row['pitch_id']}")
        # The importer deliberately preserves curated links already in videos.
        if actual["video_url"] != row["video_url"]:
            preserved.append((row["pitch_id"], actual["video_url"], row["video_url"]))
    print(f"\nVerified {len(samples)} sampled DB links and game/player identities.")
    if preserved:
        print(f"{len(preserved)} existing video URL(s) differ from automatic matches; review both:")
        for pitch_id, stored, matched in preserved:
            print(f"  {pitch_id} stored={stored} matched={matched}")
    print("Open each sample to check the MLB pitch and actual playback (not automated):")
    for row in samples:
        print(f"  {row['game_date']}  {row['pitch_id']}  {row['video_url']}")
    return len(samples)


def benchmark(connection: psycopg.Connection, season: int, repeats: int) -> None:
    """Time route handlers with real database data; skip connection/auth latency."""
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT p.pitcher_id, MAX(pl.player_name) AS name, COUNT(*) AS pitch_count
            FROM pitches p JOIN players pl ON pl.player_id = p.pitcher_id
            JOIN games g ON g.game_pk = p.game_pk WHERE g.season = %s
            GROUP BY p.pitcher_id ORDER BY pitch_count DESC LIMIT 1
            """,
            (season,),
        )
        pitcher = cursor.fetchone()
    if pitcher is None:
        raise AuditError(f"No pitcher found for season {season}")
    pitcher_id = pitcher["pitcher_id"]
    print(f"\nBenchmark pitcher: {pitcher['name']} ({pitcher['pitch_count']:,} pitches)")
    workloads = [
        ("seasons", lambda: list_seasons(connection=connection)),
        ("teams", lambda: list_teams(season=season, connection=connection)),
        (
            "pitcher search",
            lambda: search_pitchers(
                PitcherSearchFilters(season=season, q=pitcher["name"].split(",")[0]), connection
            ),
        ),
        (
            "pitcher games",
            lambda: list_pitcher_games(pitcher_id, season=season, connection=connection),
        ),
        (
            "pitch page",
            lambda: search_pitches(
                PitchFilters(season=season, pitcher_id=pitcher_id, limit=100), connection
            ),
        ),
        (
            "velocity sort",
            lambda: search_pitches(
                PitchFilters(
                    season=season,
                    pitcher_id=pitcher_id,
                    limit=100,
                    offset=500,
                    sort_by="velocity",
                    sort_order="desc",
                ),
                connection,
            ),
        ),
        (
            "aggregates",
            lambda: pitch_aggregates(
                PitchAggregateFilters(season=season, pitcher_id=pitcher_id), connection
            ),
        ),
    ]
    print("\nRoute handler       Median (ms)  Worst (ms)  Runs")
    print("------------------------------------------------")
    for name, fn in workloads:
        try:
            fn()  # Warm the server/cache before collecting repeatable samples.
            timings = []
            for _ in range(repeats):
                started = time.perf_counter()
                fn()
                timings.append((time.perf_counter() - started) * 1000)
        except psycopg.Error as exc:
            raise AuditError(f"{name} failed ({type(exc).__name__}); check its query plan") from exc
        print(f"{name:18} {statistics.median(timings):10.0f}  {max(timings):10.0f}  {repeats:4}")
    print("Timings include the Python handler and database round trips from this computer;")
    print("they exclude API Gateway, Lambda cold starts, Cognito, and browser latency.")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--expected-host", required=True, help="Exact private Neon database host")
    parser.add_argument("--report-root", type=Path, default=Path("data/processed/video_matches"))
    parser.add_argument("--season", type=int, default=2026)
    parser.add_argument("--sample-per-month", type=int, default=5)
    parser.add_argument("--repeats", type=int, default=3)
    args = parser.parse_args()
    if args.sample_per_month < 1 or args.repeats < 1:
        parser.error("--sample-per-month and --repeats must be positive")
    url = os.getenv("DATABASE_URL", "")
    host = urlparse(url).hostname if url else None
    if (
        host != args.expected_host
        or "-pooler" not in (host or "")
        or not host.endswith(".neon.tech")
    ):
        parser.error("DATABASE_URL does not point to the expected private Neon pooled endpoint")
    ranges = [
        (date(2026, 3, 25), date(2026, 3, 31)),
        (date(2026, 4, 1), date(2026, 4, 30)),
        (date(2026, 5, 1), date(2026, 5, 31)),
        (date(2026, 6, 1), date(2026, 6, 30)),
        (date(2026, 7, 1), date(2026, 7, 31)),
        (date(2026, 8, 1), date(2026, 8, 31)),
        (date(2026, 9, 1), date(2026, 9, 25)),
    ]
    try:
        with psycopg.connect(
            url, connect_timeout=10, autocommit=True, row_factory=dict_row
        ) as conn:
            with conn.cursor() as cursor:
                cursor.execute("SELECT current_database() AS name")
                if cursor.fetchone()["name"] != "baseball_video_scouting":
                    raise AuditError("Connected to a different database")
                cursor.execute("SET default_transaction_read_only = on")
                cursor.execute("SET statement_timeout = '30000ms'")
            audit_reports(conn, args.report_root, ranges, args.sample_per_month)
            benchmark(conn, args.season, args.repeats)
    except (AuditError, OSError, ValueError, psycopg.Error) as exc:
        # psycopg errors may contain a connection string: never print their text.
        print(
            f"Audit stopped: {exc if isinstance(exc, AuditError) else type(exc).__name__}",
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
