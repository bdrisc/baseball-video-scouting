"""Tests for full-result pitch aggregates used by charts and reports."""

from __future__ import annotations

from app.routers import pitches as pitch_routes
from app.schemas.filters import PitchAggregateFilters


def test_aggregates_summarize_complete_filtered_result(
    monkeypatch, scripted_connection_factory
) -> None:
    summary = {
        "total_pitches": 2,
        "average_velocity": 90.0,
        "whiffs": 1,
        "videos_available": 1,
        "pitch_types": 2,
    }
    arsenal = [
        {
            "pitch_type": "FF",
            "pitch_count": 1,
            "average_velocity": 95.0,
            "average_spin": 2400.0,
            "horizontal_break": -0.4,
            "vertical_break": 1.3,
            "swing_count": 0,
            "whiff_count": 0,
            "located_count": 1,
            "zone_count": 1,
            "balls_in_play": 0,
            "average_exit_velocity": None,
            "maximum_exit_velocity": None,
            "hard_hits": 0,
            "home_runs": 0,
        },
        {
            "pitch_type": "SL",
            "pitch_count": 1,
            "average_velocity": 85.0,
            "average_spin": 2500.0,
            "horizontal_break": 0.3,
            "vertical_break": 0.2,
            "swing_count": 1,
            "whiff_count": 1,
            "located_count": 1,
            "zone_count": 0,
            "balls_in_play": 1,
            "average_exit_velocity": 100.0,
            "maximum_exit_velocity": 100.0,
            "hard_hits": 1,
            "home_runs": 1,
        },
    ]
    velocity = [
        {
            "pitch_type": "FF",
            "inning": 1,
            "pitch_count": 1,
            "average_velocity": 95.0,
        }
    ]
    counts = [
        {
            "pitch_type": "FF",
            "balls": 0,
            "strikes": 0,
            "pitch_count": 1,
            "swing_count": 0,
            "whiff_count": 0,
            "strikeout_count": 0,
        },
        {
            "pitch_type": "SL",
            "balls": 0,
            "strikes": 2,
            "pitch_count": 1,
            "swing_count": 1,
            "whiff_count": 1,
            "strikeout_count": 1,
        },
    ]
    results = [
        {"batter_side": "L", "result_group": "Whiff", "pitch_count": 1},
        {
            "batter_side": "R",
            "result_group": "Called strike",
            "pitch_count": 1,
        },
    ]
    handedness = [
        {
            "batter_side": "L",
            "pitch_type": "SL",
            "pitch_count": 1,
            "swing_count": 1,
            "whiff_count": 1,
            "located_count": 1,
            "zone_count": 0,
        },
        {
            "batter_side": "R",
            "pitch_type": "FF",
            "pitch_count": 1,
            "swing_count": 0,
            "whiff_count": 0,
            "located_count": 1,
            "zone_count": 1,
        },
    ]
    location = [
        {
            "vertical_band": "Middle third",
            "horizontal_lane": "Center third",
            "pitch_count": 1,
            "zone_count": 1,
            "fastball_count": 1,
            "elevated_fastball_count": 0,
        },
        {
            "vertical_band": "Below zone",
            "horizontal_lane": "Right off plate",
            "pitch_count": 1,
            "zone_count": 0,
            "fastball_count": 0,
            "elevated_fastball_count": 0,
        },
    ]
    connection = scripted_connection_factory(
        [[summary], arsenal, velocity, counts, results, handedness, location]
    )
    monkeypatch.setattr(
        pitch_routes,
        "require_pitcher",
        lambda _connection, _pitcher_id: {"player_id": 7},
    )

    response = pitch_routes.pitch_aggregates(
        PitchAggregateFilters(pitcher_id=7, batter_side="l"), connection
    )

    assert response["total"] == 2
    assert response["pitch_usage"] == [
        {"pitch_type": "FF", "pitch_count": 1, "usage_percent": 50.0},
        {"pitch_type": "SL", "pitch_count": 1, "usage_percent": 50.0},
    ]
    assert response["usage_by_count"][1]["usage_percent"] == 100.0
    assert response["results_by_batter_side"][0]["percentage"] == 100.0
    assert response["report"]["usage_summary"] == "FF 50.0% · SL 50.0%"
    assert response["report"]["putaway"] == {
        "sample_size": 1,
        "top_pitch": "SL",
        "top_pitch_usage": 100.0,
        "whiff_rate": 100.0,
        "strikeouts": 1,
        "best_whiff_pitch": "SL",
    }
    assert response["report"]["damage"]["hard_hit_rate"] == 100.0
    assert response["report"]["location"]["zone_rate"] == 50.0

    assert len(connection.calls) == 7
    assert all("p.pitcher_id = %s" in call.query for call in connection.calls)
    assert all("p.batter_side = %s" in call.query for call in connection.calls)
    assert connection.calls[-1].parameters == [7, "L"]


def test_aggregate_filters_do_not_accept_pagination_controls() -> None:
    try:
        PitchAggregateFilters(pitcher_id=7, limit=500)
    except ValueError as error:
        assert "limit" in str(error)
    else:
        raise AssertionError("Aggregate filters should reject pagination controls")


def test_empty_aggregate_result_has_stable_zero_and_null_values(
    scripted_connection_factory,
) -> None:
    connection = scripted_connection_factory(
        [
            [
                {
                    "total_pitches": 0,
                    "average_velocity": None,
                    "whiffs": 0,
                    "videos_available": 0,
                    "pitch_types": 0,
                }
            ],
            [],
            [],
            [],
            [],
            [],
            [],
        ]
    )

    response = pitch_routes.pitch_aggregates(PitchAggregateFilters(), connection)

    assert response["total"] == 0
    assert response["pitch_usage"] == []
    assert response["usage_by_count"] == []
    assert response["report"]["usage_summary"] == "—"
    assert response["report"]["location"]["zone_rate"] is None
    assert response["report"]["damage"]["average_exit_velocity"] is None
