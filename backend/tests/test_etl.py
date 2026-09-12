"""Unit tests for pitch-grain cleaning and derived scouting features."""

from __future__ import annotations

import pandas as pd
import pytest

from scripts.clean_statcast import (
    join_video,
    load_savant,
    standardize_and_derive,
)


def raw_savant_rows() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "game_date": ["2026-08-07", "2026-08-07"],
            "game_pk": [824566, 824566],
            "at_bat_number": [8, 8],
            "pitch_number": [1, 2],
            "pitch_type": ["FF", "SL"],
            "pitch_name": ["4-Seam Fastball", None],
            "description": ["called_strike", "swinging_strike"],
            "events": [None, None],
            "type": ["S", "S"],
            "balls": [0, 0],
            "strikes": [0, 1],
            "zone": [5, 14],
            "plate_x": [0.1, 1.2],
            "plate_z": [2.5, 1.1],
            "sz_top": [3.4, 3.4],
            "sz_bot": [1.5, 1.5],
            "n_thruorder_pitcher": [1, 1],
            "launch_speed": [None, None],
        }
    )


def cleaned_pitches(tmp_path) -> pd.DataFrame:
    source = tmp_path / "savant.csv"
    raw_savant_rows().to_csv(source, index=False)
    return standardize_and_derive(load_savant(source))


def test_pitch_id_is_created_from_pitch_natural_key(tmp_path) -> None:
    pitches = cleaned_pitches(tmp_path)

    assert pitches["pitch_id"].tolist() == ["824566_8_1", "824566_8_2"]
    assert pitches["pitch_id"].is_unique


def test_unclassified_pitch_is_preserved_as_unknown(tmp_path) -> None:
    source = raw_savant_rows().iloc[[0]].copy()
    source["pitch_type"] = None
    path = tmp_path / "unclassified.csv"
    source.to_csv(path, index=False)

    cleaned = standardize_and_derive(load_savant(path))

    assert len(cleaned) == 1
    assert cleaned.loc[0, "pitch_id"] == "824566_8_1"
    assert cleaned.loc[0, "pitch_type"] == "unknown"
    assert cleaned.loc[0, "pitch_name"] == "4-Seam Fastball"


def test_existing_incorrect_pitch_id_stops_the_pipeline(tmp_path) -> None:
    source = raw_savant_rows()
    source["pitch_id"] = ["wrong_1", "wrong_2"]
    path = tmp_path / "bad_ids.csv"
    source.to_csv(path, index=False)

    with pytest.raises(ValueError, match="do not match"):
        load_savant(path)


def test_cleaning_standardizes_names_counts_and_missing_values(tmp_path) -> None:
    pitches = cleaned_pitches(tmp_path)

    assert pitches["pitch_name"].tolist() == ["Four-Seam Fastball", "Slider"]
    assert pitches["count"].tolist() == ["0-0", "0-1"]
    assert pitches["events"].tolist() == ["none", "none"]
    assert pitches["launch_speed"].isna().all()
    assert not pitches["is_hard_hit"].any()


def test_whiff_chase_and_count_flags_are_classified_correctly(tmp_path) -> None:
    pitches = cleaned_pitches(tmp_path)

    first, second = pitches.iloc[0], pitches.iloc[1]
    assert bool(first["is_first_pitch"]) is True
    assert bool(first["is_whiff"]) is False
    assert bool(second["is_whiff"]) is True
    assert bool(second["is_swing"]) is True
    assert bool(second["is_in_zone"]) is False
    assert bool(second["is_chase"]) is True


def test_video_join_uses_pitch_id_instead_of_row_order(tmp_path) -> None:
    pitches = cleaned_pitches(tmp_path)
    videos = pd.DataFrame(
        {
            "pitch_id": ["824566_8_2", "824566_8_1"],
            "video_url": ["https://example.com/slider", "https://example.com/fastball"],
            "video_level": ["Pitch", "Pitch"],
            "video_notes": ["whiff", "called strike"],
        }
    )

    joined = join_video(pitches, videos, require_all_video=True)

    assert joined.loc[0, "video_url"].endswith("fastball")
    assert joined.loc[1, "video_url"].endswith("slider")
    assert joined["has_video"].all()
