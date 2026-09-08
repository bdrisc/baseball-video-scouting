"""Tests for validated filters and parameterized pitch-search SQL."""

from __future__ import annotations

from app.routers import pitches as pitch_routes
from app.schemas.filters import PitchFilters


def test_combined_filters_are_passed_as_sql_parameters(
    monkeypatch, scripted_connection_factory
) -> None:
    row = {
        "total_matches": 1,
        "pitch_id": "824566_10_5",
        "pitch_type": "SL",
        "balls": 1,
        "strikes": 2,
        "batter_side": "R",
    }
    connection = scripted_connection_factory([[row]])
    monkeypatch.setattr(
        pitch_routes,
        "require_pitcher",
        lambda _connection, _pitcher_id: {"player_id": 7},
    )
    filters = PitchFilters(
        pitcher_id=7,
        pitch_type="sl",
        balls=1,
        strikes=2,
        batter_side="r",
        result="swinging_strike",
        min_velocity=82,
        max_velocity=89,
        video_available=True,
    )

    response = pitch_routes.search_pitches(filters, connection)

    call = connection.calls[-1]
    assert response["total"] == 1
    assert response["pitches"][0]["pitch_id"] == "824566_10_5"
    assert "p.pitch_type = %s" in call.query
    assert "p.balls = %s" in call.query
    assert "p.strikes = %s" in call.query
    assert "COALESCE(v.video_available, FALSE) = %s" in call.query
    assert "swinging_strike" not in call.query
    assert call.parameters == [
        7,
        "SL",
        1,
        2,
        "R",
        82.0,
        89.0,
        "swinging_strike",
        "swinging_strike",
        True,
        100,
        0,
    ]


def test_lowercase_filter_codes_are_normalized() -> None:
    filters = PitchFilters(pitch_type="ff", batter_side="l")

    assert filters.pitch_type.value == "FF"
    assert filters.batter_side.value == "L"
