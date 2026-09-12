"""Tests for the one-command manual Savant ingestion workflow."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from scripts.ingest_savant import ingest_savant, validate_expected_season


def write_raw_export(path: Path) -> None:
    pd.DataFrame(
        [
            {
                "game_date": "2026-04-01",
                "game_pk": 900001,
                "game_type": "R",
                "at_bat_number": 1,
                "pitch_number": 1,
                "inning": 1,
                "inning_topbot": "Top",
                "outs_when_up": 0,
                "home_team": "BOS",
                "away_team": "NYY",
                "player_name": "Example, Pitcher",
                "pitcher": 800001,
                "batter": 700001,
                "stand": "R",
                "p_throws": "L",
                "balls": 0,
                "strikes": 0,
                "pitch_type": "FF",
                "pitch_name": "4-Seam Fastball",
                "description": "called_strike",
                "events": None,
                "type": "S",
                "bb_type": None,
                "zone": 5,
                "release_speed": 95.1,
                "effective_speed": 96.0,
                "release_spin_rate": 2400,
                "release_extension": 6.5,
                "release_pos_x": 1.8,
                "release_pos_y": 54.0,
                "release_pos_z": 5.9,
                "pfx_x": -0.4,
                "pfx_z": 1.4,
                "plate_x": 0.1,
                "plate_z": 2.6,
                "sz_top": 3.4,
                "sz_bot": 1.5,
                "arm_angle": 45.0,
                "launch_speed": None,
                "launch_angle": None,
                "n_thruorder_pitcher": 1,
            }
        ]
    ).to_csv(path, index=False)


def test_dry_run_cleans_export_without_requiring_video_or_database(
    tmp_path: Path,
) -> None:
    source = tmp_path / "april.csv"
    output = tmp_path / "april_cleaned.csv"
    write_raw_export(source)

    report = ingest_savant(
        source,
        output=output,
        expected_season=2026,
        dry_run=True,
    )

    cleaned = pd.read_csv(output)
    assert report is None
    assert cleaned["pitch_id"].tolist() == ["900001_1_1"]
    assert not cleaned["has_video"].any()


def test_expected_season_guard_rejects_the_wrong_export() -> None:
    data = pd.DataFrame({"game_date": ["2025-09-28", "2026-04-01"]})

    with pytest.raises(ValueError, match="also contains season.*2025"):
        validate_expected_season(data, 2026)


def test_ingestion_passes_database_url_to_atomic_loader(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = tmp_path / "may.csv"
    write_raw_export(source)
    captured: dict[str, object] = {}
    expected_report = {"database": "baseball_video_scouting"}

    def fake_load(data: pd.DataFrame, **kwargs: object) -> dict[str, object]:
        captured["rows"] = len(data)
        captured.update(kwargs)
        return expected_report

    monkeypatch.setattr("scripts.ingest_savant.load_database", fake_load)
    monkeypatch.setattr("scripts.ingest_savant.print_report", lambda report: None)

    report = ingest_savant(
        source,
        output=tmp_path / "cleaned.csv",
        database_url="postgresql://example.invalid/baseball_video_scouting",
        expected_season=2026,
    )

    assert report == expected_report
    assert captured["rows"] == 1
    assert captured["connection_string"].startswith("postgresql://")
