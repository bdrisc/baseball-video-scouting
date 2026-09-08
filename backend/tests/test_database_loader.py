"""Tests for relational record mapping and idempotent SQL definitions."""

from __future__ import annotations

import pandas as pd
import pytest

from scripts.load_database import (
    GAME_UPSERT_SQL,
    PITCH_UPSERT_SQL,
    PLAYER_UPSERT_SQL,
    VIDEO_UPSERT_SQL,
    LoaderError,
    load_cleaned_csv,
    prepare_games,
    prepare_pitches,
    prepare_players,
    prepare_videos,
)


def cleaned_row() -> dict:
    return {
        "pitch_id": "824566_8_1",
        "game_pk": 824566,
        "game_date": "2026-08-07",
        "home_team": "CLE",
        "away_team": "CWS",
        "player_name": "Messick, Parker",
        "pitcher": 800048,
        "batter": 700001,
        "p_throws": "L",
        "stand": "R",
        "at_bat_number": 8,
        "pitch_number": 1,
        "inning": 1,
        "inning_topbot": "Top",
        "pitch_type": "FF",
        "release_speed": 94.0,
        "release_spin_rate": 2350.0,
        "pfx_x": -0.4,
        "pfx_z": 1.3,
        "release_extension": 6.5,
        "plate_x": 0.1,
        "plate_z": 2.6,
        "balls": 0,
        "strikes": 0,
        "description": "called_strike",
        "events": "none",
        "launch_speed": None,
        "launch_angle": None,
        "has_video": True,
        "video_url": "https://www.mlb.com/video/example",
        "video_level": "Pitch",
        "video_notes": "First-pitch fastball",
    }


def test_cleaned_rows_map_to_relational_parent_and_child_records() -> None:
    data = pd.DataFrame([cleaned_row()])
    data["game_date"] = pd.to_datetime(data["game_date"]).dt.date

    players = prepare_players(data)
    games = prepare_games(data)
    pitches = prepare_pitches(data, {800048: 10, 700001: 11})
    videos = prepare_videos(data)

    assert {record["mlb_id"] for record in players} == {800048, 700001}
    assert games == [
        {
            "game_pk": 824566,
            "game_date": pd.Timestamp("2026-08-07").date(),
            "home_team": "CLE",
            "away_team": "CWS",
        }
    ]
    assert pitches[0]["pitcher_id"] == 10
    assert pitches[0]["batter_id"] == 11
    assert pitches[0]["events"] is None
    assert videos[0]["pitch_id"] == "824566_8_1"
    assert videos[0]["notes"] == "First-pitch fastball"


def test_loader_rejects_duplicate_pitch_ids(tmp_path) -> None:
    duplicated = pd.DataFrame([cleaned_row(), cleaned_row()])
    path = tmp_path / "duplicates.csv"
    duplicated.to_csv(path, index=False)

    with pytest.raises(LoaderError, match="duplicate pitch IDs"):
        load_cleaned_csv(path)


def test_upserts_are_parameterized_and_idempotent() -> None:
    statements = [PLAYER_UPSERT_SQL, GAME_UPSERT_SQL, PITCH_UPSERT_SQL, VIDEO_UPSERT_SQL]

    assert all("ON CONFLICT" in statement for statement in statements)
    assert "%(pitch_id)s" in PITCH_UPSERT_SQL
    assert "%(video_url)s" in VIDEO_UPSERT_SQL
    assert "ON CONFLICT (mlb_id)" in PLAYER_UPSERT_SQL
