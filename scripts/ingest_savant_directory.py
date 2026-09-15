#!/usr/bin/env python3
"""Load a directory of Statcast CSV files with durable batch and error history."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

import pandas as pd
import psycopg

from scripts.ingest_savant import ingest_savant
from scripts.load_database import LoaderError


class BatchIngestionError(RuntimeError):
    """Raised when a batch run cannot start or its tracking cannot be saved."""


@dataclass
class BatchSummary:
    """Counts reported after processing a directory."""

    discovered: int = 0
    succeeded: int = 0
    failed: int = 0
    skipped: int = 0
    pitch_rows: int = 0


def sha256_file(path: Path) -> str:
    """Return a streaming SHA-256 digest without loading the whole CSV in memory."""
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def discover_csv_files(input_dir: Path, pattern: str) -> list[Path]:
    """Return stable, file-only input ordering."""
    if not input_dir.is_dir():
        raise BatchIngestionError(f"Input directory not found: {input_dir}")
    files = sorted(path for path in input_dir.glob(pattern) if path.is_file())
    if not files:
        raise BatchIngestionError(
            f"No CSV files matching {pattern!r} were found in {input_dir}."
        )
    return files


def safe_error_message(error: Exception, database_url: str) -> str:
    """Create a bounded log message without retaining the database credential."""
    message = str(error).replace(database_url, "[DATABASE_URL redacted]")
    return message[:4000] or error.__class__.__name__


class ImportTracker:
    """Persist import status independently from each atomic pitch load."""

    def __init__(self, database_url: str):
        self.database_url = database_url

    def _connect(self) -> psycopg.Connection[Any]:
        return psycopg.connect(self.database_url, connect_timeout=10, autocommit=True)

    def verify_schema(self) -> None:
        with self._connect() as connection, connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT
                    to_regclass('public.import_batches'),
                    to_regclass('public.import_errors')
                """
            )
            batch_table, error_table = cursor.fetchone()
        if batch_table is None or error_table is None:
            raise BatchIngestionError(
                "Import tracking tables are missing. Apply "
                "database/migrations/002_import_batch_logging.sql first."
            )

    def successful_batch_exists(self, source_sha256: str) -> bool:
        with self._connect() as connection, connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT EXISTS (
                    SELECT 1
                    FROM import_batches
                    WHERE source_sha256 = %s
                      AND status = 'succeeded'
                )
                """,
                (source_sha256,),
            )
            return bool(cursor.fetchone()[0])

    def start_batch(
        self,
        *,
        source_file: str,
        source_sha256: str,
        source_size_bytes: int,
        expected_season: int | None,
    ) -> int:
        with self._connect() as connection, connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO import_batches (
                    source_file,
                    source_sha256,
                    source_size_bytes,
                    expected_season,
                    status
                )
                VALUES (%s, %s, %s, %s, 'running')
                RETURNING import_batch_id
                """,
                (
                    source_file,
                    source_sha256,
                    source_size_bytes,
                    expected_season,
                ),
            )
            return int(cursor.fetchone()[0])

    def mark_succeeded(self, batch_id: int, report: dict[str, Any]) -> None:
        source = report["source"]
        new = report["new"]
        existing = report["existing"]
        with self._connect() as connection, connection.cursor() as cursor:
            cursor.execute(
                """
                UPDATE import_batches
                SET
                    status = 'succeeded',
                    rows_loaded = %s,
                    new_pitches = %s,
                    existing_pitches = %s,
                    finished_at = CURRENT_TIMESTAMP
                WHERE import_batch_id = %s
                  AND status = 'running'
                """,
                (
                    int(source["pitches"]),
                    int(new["pitches"]),
                    int(existing["pitches"]),
                    batch_id,
                ),
            )
            if cursor.rowcount != 1:
                raise BatchIngestionError(
                    f"Could not mark import batch {batch_id} as succeeded."
                )

    def mark_failed(
        self,
        batch_id: int,
        *,
        error_type: str,
        error_message: str,
        source_file: str,
    ) -> None:
        context = json.dumps({"source_file": source_file})
        with self._connect() as connection:
            with connection.transaction():
                with connection.cursor() as cursor:
                    cursor.execute(
                        """
                        INSERT INTO import_errors (
                            import_batch_id,
                            error_type,
                            error_message,
                            error_context
                        )
                        VALUES (%s, %s, %s, %s::JSONB)
                        """,
                        (batch_id, error_type[:100], error_message, context),
                    )
                    cursor.execute(
                        """
                        UPDATE import_batches
                        SET
                            status = 'failed',
                            error_count = error_count + 1,
                            finished_at = CURRENT_TIMESTAMP
                        WHERE import_batch_id = %s
                          AND status = 'running'
                        """,
                        (batch_id,),
                    )
                    if cursor.rowcount != 1:
                        raise BatchIngestionError(
                            f"Could not mark import batch {batch_id} as failed."
                        )


def ingest_directory(
    input_dir: Path,
    *,
    database_url: str,
    expected_season: int | None,
    pattern: str = "statcast_*.csv",
    output_dir: Path = Path("data/processed"),
    force: bool = False,
    stop_on_error: bool = False,
    tracker: ImportTracker | None = None,
    ingest: Callable[..., dict[str, Any] | None] = ingest_savant,
) -> BatchSummary:
    """Load every matching CSV while recording one independently retryable attempt."""
    files = discover_csv_files(input_dir, pattern)
    active_tracker = tracker or ImportTracker(database_url)
    active_tracker.verify_schema()
    output_dir.mkdir(parents=True, exist_ok=True)
    summary = BatchSummary(discovered=len(files))

    for source_file in files:
        source_hash = sha256_file(source_file)
        if not force and active_tracker.successful_batch_exists(source_hash):
            summary.skipped += 1
            print(f"Skipped {source_file.name}: this exact file already succeeded.")
            continue

        batch_id = active_tracker.start_batch(
            source_file=source_file.name,
            source_sha256=source_hash,
            source_size_bytes=source_file.stat().st_size,
            expected_season=expected_season,
        )
        output = output_dir / f"{source_file.stem}_cleaned.csv"
        print(f"\nImport batch {batch_id}: {source_file.name}")

        try:
            report = ingest(
                source_file,
                output=output,
                database_url=database_url,
                expected_season=expected_season,
            )
            if report is None:
                raise BatchIngestionError(
                    "The ingestion returned no database report."
                )
            active_tracker.mark_succeeded(batch_id, report)
        except Exception as exc:
            message = safe_error_message(exc, database_url)
            active_tracker.mark_failed(
                batch_id,
                error_type=exc.__class__.__name__,
                error_message=message,
                source_file=source_file.name,
            )
            summary.failed += 1
            print(
                f"Failed {source_file.name}: {message} "
                f"(recorded in import batch {batch_id})",
                file=sys.stderr,
            )
            if stop_on_error:
                break
            continue

        rows = int(report["source"]["pitches"])
        summary.succeeded += 1
        summary.pitch_rows += rows
        print(f"Completed import batch {batch_id}: {rows:,} pitch rows.")

    return summary


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Clean and load a directory of daily Statcast CSV files while "
            "recording durable import status and errors in PostgreSQL."
        )
    )
    parser.add_argument("--input-dir", required=True, type=Path)
    parser.add_argument(
        "--pattern",
        default="statcast_*.csv",
        help="Input filename pattern (default: statcast_*.csv).",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("data/processed"),
        help="Cleaned CSV destination (default: data/processed).",
    )
    parser.add_argument("--expected-season", type=int)
    parser.add_argument(
        "--force",
        action="store_true",
        help="Import files even when the same SHA-256 hash previously succeeded.",
    )
    parser.add_argument(
        "--stop-on-error",
        action="store_true",
        help="Stop after the first failed file instead of continuing.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        print(
            "Batch ingestion stopped: DATABASE_URL must be set in the current "
            "PowerShell session.",
            file=sys.stderr,
        )
        raise SystemExit(1)

    try:
        summary = ingest_directory(
            args.input_dir,
            database_url=database_url,
            expected_season=args.expected_season,
            pattern=args.pattern,
            output_dir=args.output_dir,
            force=args.force,
            stop_on_error=args.stop_on_error,
        )
    except (BatchIngestionError, LoaderError, OSError, ValueError, pd.errors.ParserError) as exc:
        print(f"Batch ingestion stopped: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
    except psycopg.OperationalError as exc:
        print(
            "Batch ingestion stopped: PostgreSQL could not be reached.",
            file=sys.stderr,
        )
        raise SystemExit(1) from exc

    print("\nBatch ingestion complete")
    print(f"Files discovered: {summary.discovered:,}")
    print(f"Files succeeded: {summary.succeeded:,}")
    print(f"Files skipped: {summary.skipped:,}")
    print(f"Files failed: {summary.failed:,}")
    print(f"Pitch rows loaded: {summary.pitch_rows:,}")

    if summary.failed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
