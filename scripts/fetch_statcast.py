#!/usr/bin/env python3
"""Download league-wide Baseball Savant Statcast data in resumable daily files."""

from __future__ import annotations

import argparse
import sys
import time
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path

import pandas as pd

REQUIRED_COLUMNS = {
    "game_date",
    "game_pk",
    "at_bat_number",
    "pitch_number",
    "pitcher",
    "batter",
}
PITCH_KEY = ["game_pk", "at_bat_number", "pitch_number"]


class DownloadError(RuntimeError):
    """Raised when Statcast data cannot be downloaded or validated."""


@dataclass
class DownloadSummary:
    """Counters reported after a download run."""

    downloaded_days: int = 0
    skipped_days: int = 0
    empty_days: int = 0
    rows: int = 0


def parse_iso_date(value: str) -> date:
    """Parse a YYYY-MM-DD command-line date."""
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError as exc:
        raise argparse.ArgumentTypeError(
            f"{value!r} is not a valid date; use YYYY-MM-DD."
        ) from exc


def iter_dates(start_date: date, end_date: date) -> Iterator[date]:
    """Yield every calendar date in an inclusive range."""
    current = start_date
    while current <= end_date:
        yield current
        current += timedelta(days=1)


def default_fetcher(game_date: date) -> pd.DataFrame:
    """Fetch one day of league-wide pitch data through pybaseball."""
    from pybaseball import statcast

    value = game_date.isoformat()
    return statcast(
        start_dt=value,
        end_dt=value,
        verbose=False,
        parallel=False,
    )


def validate_day(data: pd.DataFrame, expected_date: date) -> pd.DataFrame:
    """Validate, deduplicate, and consistently order one downloaded day."""
    if data.empty:
        return data.copy()

    missing = sorted(REQUIRED_COLUMNS - set(data.columns))
    if missing:
        raise DownloadError(
            "The Statcast response is missing required columns: "
            + ", ".join(missing)
        )

    normalized = data.copy()
    returned_dates = pd.to_datetime(normalized["game_date"], errors="raise").dt.date
    wrong_dates = sorted({value.isoformat() for value in returned_dates if value != expected_date})
    if wrong_dates:
        raise DownloadError(
            f"Requested {expected_date.isoformat()}, but the response also contained: "
            + ", ".join(wrong_dates)
        )

    missing_keys = normalized[PITCH_KEY].isna().any(axis=1)
    if missing_keys.any():
        raise DownloadError(
            f"The Statcast response contains {int(missing_keys.sum()):,} rows "
            "without a complete pitch key."
        )

    duplicate_keys = normalized.duplicated(PITCH_KEY, keep=False)
    if duplicate_keys.any():
        conflicting = (
            normalized.loc[duplicate_keys]
            .groupby(PITCH_KEY, dropna=False)
            .nunique(dropna=False)
            .gt(1)
            .any(axis=1)
        )
        if conflicting.any():
            raise DownloadError(
                f"The Statcast response contains {int(conflicting.sum()):,} "
                "conflicting pitch keys."
            )
        normalized = normalized.drop_duplicates(PITCH_KEY, keep="last")

    return normalized.sort_values(PITCH_KEY, kind="stable").reset_index(drop=True)


def day_csv_path(output_dir: Path, game_date: date) -> Path:
    """Return the raw CSV path for one date."""
    return output_dir / f"statcast_{game_date.isoformat()}.csv"


def empty_marker_path(output_dir: Path, game_date: date) -> Path:
    """Return the completion marker used for a date with no pitches."""
    return output_dir / f"statcast_{game_date.isoformat()}.empty"


def validate_existing_file(path: Path, expected_date: date) -> int:
    """Validate a previously downloaded CSV before treating it as complete."""
    try:
        existing = pd.read_csv(path)
        validated = validate_day(existing, expected_date)
    except (OSError, ValueError, pd.errors.ParserError) as exc:
        raise DownloadError(f"Existing file is invalid: {path}") from exc
    return len(validated)


def write_day_atomic(data: pd.DataFrame, path: Path) -> None:
    """Write a CSV through a temporary file so interrupted writes are not retained."""
    temporary = path.with_suffix(".csv.part")
    try:
        data.to_csv(temporary, index=False)
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def fetch_statcast_range(
    start_date: date,
    end_date: date,
    output_dir: Path,
    *,
    force: bool = False,
    retries: int = 3,
    retry_delay: float = 5.0,
    request_delay: float = 1.0,
    fetcher: Callable[[date], pd.DataFrame] = default_fetcher,
    sleep: Callable[[float], None] = time.sleep,
) -> DownloadSummary:
    """Download an inclusive date range as independently resumable daily files."""
    if end_date < start_date:
        raise DownloadError("The end date must be on or after the start date.")
    if end_date > date.today():
        raise DownloadError("The end date cannot be in the future.")
    if retries < 1:
        raise DownloadError("Retries must be at least 1.")
    if retry_delay < 0 or request_delay < 0:
        raise DownloadError("Delay values cannot be negative.")

    output_dir.mkdir(parents=True, exist_ok=True)
    summary = DownloadSummary()

    for game_date in iter_dates(start_date, end_date):
        csv_path = day_csv_path(output_dir, game_date)
        empty_path = empty_marker_path(output_dir, game_date)

        if not force and csv_path.exists():
            rows = validate_existing_file(csv_path, game_date)
            summary.skipped_days += 1
            summary.rows += rows
            print(f"Skipped {game_date}: existing validated file ({rows:,} rows)")
            continue
        if not force and empty_path.exists():
            summary.skipped_days += 1
            summary.empty_days += 1
            print(f"Skipped {game_date}: existing empty-day marker")
            continue

        data: pd.DataFrame | None = None
        for attempt in range(1, retries + 1):
            try:
                data = validate_day(fetcher(game_date), game_date)
                break
            except Exception as exc:
                if attempt == retries:
                    raise DownloadError(
                        f"Failed to download {game_date} after {retries} attempts."
                    ) from exc
                wait_seconds = retry_delay * (2 ** (attempt - 1))
                print(
                    f"Attempt {attempt}/{retries} failed for {game_date}; "
                    f"retrying in {wait_seconds:g} seconds.",
                    file=sys.stderr,
                )
                sleep(wait_seconds)

        if data is None:
            raise DownloadError(f"No result was returned for {game_date}.")

        csv_path.unlink(missing_ok=True)
        empty_path.unlink(missing_ok=True)
        if data.empty:
            empty_path.write_text(
                "No Statcast pitches were returned for this date.\n",
                encoding="utf-8",
            )
            summary.empty_days += 1
            print(f"Downloaded {game_date}: no pitches")
        else:
            write_day_atomic(data, csv_path)
            summary.rows += len(data)
            print(f"Downloaded {game_date}: {len(data):,} rows")

        summary.downloaded_days += 1
        if game_date != end_date and request_delay:
            sleep(request_delay)

    return summary


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Download league-wide Statcast pitch data into resumable daily CSV files. "
            "Run the existing ingestion command separately after reviewing the files."
        )
    )
    parser.add_argument("--start-date", required=True, type=parse_iso_date)
    parser.add_argument("--end-date", required=True, type=parse_iso_date)
    parser.add_argument(
        "--output-dir",
        type=Path,
        help="Destination directory (default: data/raw/statcast/<start year>).",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Redownload dates even when a completed daily file or marker exists.",
    )
    parser.add_argument("--retries", type=int, default=3)
    parser.add_argument("--retry-delay", type=float, default=5.0)
    parser.add_argument(
        "--request-delay",
        type=float,
        default=1.0,
        help="Polite delay between successful daily requests (default: 1 second).",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    output_dir = args.output_dir or Path("data/raw/statcast") / str(args.start_date.year)
    try:
        summary = fetch_statcast_range(
            args.start_date,
            args.end_date,
            output_dir,
            force=args.force,
            retries=args.retries,
            retry_delay=args.retry_delay,
            request_delay=args.request_delay,
        )
    except (DownloadError, OSError, ValueError, pd.errors.ParserError) as exc:
        print(f"Download stopped: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc

    print("\nStatcast download complete")
    print(f"Output directory: {output_dir.resolve()}")
    print(f"Dates downloaded: {summary.downloaded_days:,}")
    print(f"Dates skipped: {summary.skipped_days:,}")
    print(f"Empty dates: {summary.empty_days:,}")
    print(f"Pitch rows available: {summary.rows:,}")


if __name__ == "__main__":
    main()
