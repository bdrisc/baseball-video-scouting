"""Tests for the resumable league-wide Statcast downloader."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pandas as pd
import pytest

from scripts.fetch_statcast import (
    DownloadError,
    day_csv_path,
    empty_marker_path,
    fetch_statcast_range,
)


def statcast_row(game_date: date, pitch_number: int = 1) -> dict[str, object]:
    return {
        "game_date": game_date.isoformat(),
        "game_pk": 900001,
        "at_bat_number": 1,
        "pitch_number": pitch_number,
        "pitcher": 800001,
        "batter": 700001,
        "pitch_type": "FF",
    }


def test_downloads_daily_files_and_marks_empty_days(tmp_path: Path) -> None:
    calls: list[date] = []

    def fake_fetcher(game_date: date) -> pd.DataFrame:
        calls.append(game_date)
        if game_date == date(2026, 4, 2):
            return pd.DataFrame()
        return pd.DataFrame([statcast_row(game_date)])

    summary = fetch_statcast_range(
        date(2026, 4, 1),
        date(2026, 4, 3),
        tmp_path,
        fetcher=fake_fetcher,
        sleep=lambda seconds: None,
        request_delay=0,
    )

    assert calls == [date(2026, 4, 1), date(2026, 4, 2), date(2026, 4, 3)]
    assert summary.downloaded_days == 3
    assert summary.empty_days == 1
    assert summary.rows == 2
    assert day_csv_path(tmp_path, date(2026, 4, 1)).exists()
    assert empty_marker_path(tmp_path, date(2026, 4, 2)).exists()


def test_rerun_skips_and_validates_completed_dates(tmp_path: Path) -> None:
    game_date = date(2026, 5, 1)
    pd.DataFrame([statcast_row(game_date)]).to_csv(
        day_csv_path(tmp_path, game_date),
        index=False,
    )

    def unexpected_fetcher(requested_date: date) -> pd.DataFrame:
        raise AssertionError(f"Unexpected download for {requested_date}")

    summary = fetch_statcast_range(
        game_date,
        game_date,
        tmp_path,
        fetcher=unexpected_fetcher,
        sleep=lambda seconds: None,
    )

    assert summary.downloaded_days == 0
    assert summary.skipped_days == 1
    assert summary.rows == 1


def test_retries_temporary_failure_then_writes_file(tmp_path: Path) -> None:
    game_date = date(2026, 6, 1)
    attempts = 0
    delays: list[float] = []

    def flaky_fetcher(requested_date: date) -> pd.DataFrame:
        nonlocal attempts
        attempts += 1
        if attempts < 3:
            raise ConnectionError("temporary failure")
        return pd.DataFrame([statcast_row(requested_date)])

    summary = fetch_statcast_range(
        game_date,
        game_date,
        tmp_path,
        retries=3,
        retry_delay=2,
        request_delay=0,
        fetcher=flaky_fetcher,
        sleep=delays.append,
    )

    assert attempts == 3
    assert delays == [2, 4]
    assert summary.rows == 1


def test_rejects_response_from_wrong_date(tmp_path: Path) -> None:
    requested_date = date(2026, 7, 1)

    with pytest.raises(DownloadError, match="Failed to download"):
        fetch_statcast_range(
            requested_date,
            requested_date,
            tmp_path,
            retries=1,
            fetcher=lambda game_date: pd.DataFrame(
                [statcast_row(date(2026, 7, 2))]
            ),
            sleep=lambda seconds: None,
        )


def test_deduplicates_identical_pitch_keys(tmp_path: Path) -> None:
    game_date = date(2026, 8, 1)
    row = statcast_row(game_date)

    summary = fetch_statcast_range(
        game_date,
        game_date,
        tmp_path,
        fetcher=lambda requested_date: pd.DataFrame([row, row]),
        sleep=lambda seconds: None,
    )

    saved = pd.read_csv(day_csv_path(tmp_path, game_date))
    assert summary.rows == 1
    assert len(saved) == 1
