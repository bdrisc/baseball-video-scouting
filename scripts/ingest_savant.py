#!/usr/bin/env python3
"""Clean, validate, and idempotently load one manual Savant CSV export."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from typing import Any

import pandas as pd
import psycopg

from scripts.clean_statcast import build_dataset
from scripts.load_database import LoaderError, load_database, print_report


def default_output_path(savant_csv: Path) -> Path:
    """Return a traceable processed path without writing beside the raw export."""
    return Path("data/processed") / f"{savant_csv.stem}_cleaned.csv"


def validate_expected_season(data: pd.DataFrame, expected_season: int | None) -> None:
    """Reject a CSV containing dates outside the intended season."""
    if expected_season is None:
        return

    years = pd.to_datetime(data["game_date"], errors="raise").dt.year
    unexpected = sorted(int(year) for year in years.unique() if year != expected_season)
    if unexpected:
        raise LoaderError(
            f"Expected only {expected_season} data, but the CSV also contains "
            f"season(s): {', '.join(map(str, unexpected))}."
        )


def ingest_savant(
    savant_csv: Path,
    *,
    output: Path | None = None,
    database_url: str | None = None,
    video_table: Path | None = None,
    video_sheet: str = "Video Links",
    require_all_video: bool = False,
    expected_season: int | None = None,
    dry_run: bool = False,
) -> dict[str, Any] | None:
    """Run the complete CSV-to-PostgreSQL workflow."""
    cleaned_output = output or default_output_path(savant_csv)
    cleaned = build_dataset(
        savant_csv=savant_csv,
        video_table=video_table,
        output=cleaned_output,
        video_sheet=video_sheet,
        require_all_video=require_all_video,
    )
    validate_expected_season(cleaned, expected_season)

    print(f"Validated source: {savant_csv.resolve()}")
    print(f"Wrote cleaned dataset: {cleaned_output.resolve()}")
    print(f"Rows ready: {len(cleaned):,}")
    print(f"Games: {cleaned['game_pk'].nunique():,}")
    print(f"Pitchers: {cleaned['pitcher'].nunique():,}")
    print(f"Date range: {cleaned['game_date'].min()} through {cleaned['game_date'].max()}")
    print(
        "Video coverage: "
        f"{int(cleaned['has_video'].sum()):,}/{len(cleaned):,} "
        f"({cleaned['has_video'].mean():.1%})"
    )

    if dry_run:
        print("Dry run complete: PostgreSQL was not changed.")
        return None
    if not database_url:
        raise LoaderError(
            "DATABASE_URL is required unless --dry-run is used. "
            "Set it in the current PowerShell session; do not put it in the command."
        )

    report = load_database(cleaned, connection_string=database_url)
    print_report(report)
    return report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Clean, validate, and idempotently load one manual Baseball Savant "
            "CSV export into PostgreSQL."
        )
    )
    parser.add_argument(
        "--savant-csv",
        required=True,
        type=Path,
        help="Raw CSV exported manually from Baseball Savant.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="Optional cleaned CSV path (default: data/processed/<source>_cleaned.csv).",
    )
    parser.add_argument(
        "--expected-season",
        type=int,
        help="Reject rows outside this season, for example 2026.",
    )
    parser.add_argument(
        "--video-table",
        type=Path,
        help="Optional pitch-keyed video table; omit until video matching is complete.",
    )
    parser.add_argument(
        "--video-sheet",
        default="Video Links",
        help="Excel sheet containing video links (default: Video Links).",
    )
    parser.add_argument(
        "--require-all-video",
        action="store_true",
        help="Reject any pitch without video; requires --video-table.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Clean and validate the export without changing PostgreSQL.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    try:
        ingest_savant(
            savant_csv=args.savant_csv,
            output=args.output,
            database_url=os.getenv("DATABASE_URL"),
            video_table=args.video_table,
            video_sheet=args.video_sheet,
            require_all_video=args.require_all_video,
            expected_season=args.expected_season,
            dry_run=args.dry_run,
        )
    except (LoaderError, ValueError, pd.errors.ParserError) as exc:
        print(f"Ingestion stopped: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
    except psycopg.OperationalError as exc:
        print(
            "Could not connect to PostgreSQL. Confirm DATABASE_URL is current "
            "and the database is reachable.",
            file=sys.stderr,
        )
        raise SystemExit(1) from exc
    except psycopg.Error as exc:
        print(
            "PostgreSQL rejected the ingestion. The transaction was rolled back; "
            "no partial load was saved.",
            file=sys.stderr,
        )
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
