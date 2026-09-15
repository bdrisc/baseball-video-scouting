"""Tests for tracked directory-wide Statcast ingestion."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from scripts.ingest_savant_directory import (
    BatchIngestionError,
    ingest_directory,
    safe_error_message,
    sha256_file,
)


class FakeTracker:
    def __init__(self, successful_hashes: set[str] | None = None):
        self.successful_hashes = successful_hashes or set()
        self.started: list[dict[str, Any]] = []
        self.succeeded: list[tuple[int, dict[str, Any]]] = []
        self.failed: list[tuple[int, dict[str, str]]] = []
        self.schema_verified = False

    def verify_schema(self) -> None:
        self.schema_verified = True

    def successful_batch_exists(self, source_sha256: str) -> bool:
        return source_sha256 in self.successful_hashes

    def start_batch(self, **values: Any) -> int:
        self.started.append(values)
        return len(self.started)

    def mark_succeeded(self, batch_id: int, report: dict[str, Any]) -> None:
        self.succeeded.append((batch_id, report))

    def mark_failed(self, batch_id: int, **values: str) -> None:
        self.failed.append((batch_id, values))


def report(rows: int, new_pitches: int = 0) -> dict[str, Any]:
    return {
        "source": {"pitches": rows},
        "new": {"pitches": new_pitches},
        "existing": {"pitches": rows - new_pitches},
    }


def test_directory_run_succeeds_skips_and_records_failure(tmp_path: Path) -> None:
    first = tmp_path / "statcast_2026-04-01.csv"
    second = tmp_path / "statcast_2026-04-02.csv"
    third = tmp_path / "statcast_2026-04-03.csv"
    first.write_text("first", encoding="utf-8")
    second.write_text("second", encoding="utf-8")
    third.write_text("third", encoding="utf-8")
    tracker = FakeTracker({sha256_file(first)})
    ingested: list[str] = []

    def fake_ingest(source: Path, **kwargs: Any) -> dict[str, Any]:
        ingested.append(source.name)
        if source == third:
            raise ValueError("bad daily file")
        assert kwargs["expected_season"] == 2026
        assert kwargs["database_url"] == "postgresql://secret"
        return report(4200, new_pitches=4200)

    summary = ingest_directory(
        tmp_path,
        database_url="postgresql://secret",
        expected_season=2026,
        tracker=tracker,
        ingest=fake_ingest,
    )

    assert tracker.schema_verified
    assert summary.discovered == 3
    assert summary.skipped == 1
    assert summary.succeeded == 1
    assert summary.failed == 1
    assert summary.pitch_rows == 4200
    assert ingested == [second.name, third.name]
    assert len(tracker.started) == 2
    assert tracker.started[0]["source_file"] == second.name
    assert tracker.succeeded[0][0] == 1
    assert tracker.failed[0][0] == 2
    assert tracker.failed[0][1]["error_type"] == "ValueError"


def test_force_reprocesses_a_successful_hash(tmp_path: Path) -> None:
    source = tmp_path / "statcast_2026-05-01.csv"
    source.write_text("source", encoding="utf-8")
    tracker = FakeTracker({sha256_file(source)})

    summary = ingest_directory(
        tmp_path,
        database_url="postgresql://secret",
        expected_season=2026,
        force=True,
        tracker=tracker,
        ingest=lambda source, **kwargs: report(100, new_pitches=0),
    )

    assert summary.succeeded == 1
    assert summary.skipped == 0
    assert len(tracker.started) == 1


def test_stop_on_error_does_not_start_later_files(tmp_path: Path) -> None:
    for day in (1, 2):
        (tmp_path / f"statcast_2026-06-0{day}.csv").write_text(
            str(day),
            encoding="utf-8",
        )
    tracker = FakeTracker()

    summary = ingest_directory(
        tmp_path,
        database_url="postgresql://secret",
        expected_season=2026,
        stop_on_error=True,
        tracker=tracker,
        ingest=lambda source, **kwargs: (_ for _ in ()).throw(ValueError("stop")),
    )

    assert summary.failed == 1
    assert len(tracker.started) == 1


def test_error_message_redacts_database_url_and_is_bounded() -> None:
    database_url = "postgresql://user:password@example.test/database"
    error = ValueError(f"Could not use {database_url} " + ("x" * 5000))

    message = safe_error_message(error, database_url)

    assert database_url not in message
    assert "[DATABASE_URL redacted]" in message
    assert len(message) == 4000


def test_missing_input_directory_stops_before_tracking(tmp_path: Path) -> None:
    with __import__("pytest").raises(BatchIngestionError, match="Input directory"):
        ingest_directory(
            tmp_path / "missing",
            database_url="postgresql://secret",
            expected_season=2026,
            tracker=FakeTracker(),
            ingest=lambda source, **kwargs: report(1),
        )
