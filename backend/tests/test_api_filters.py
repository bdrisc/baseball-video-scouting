"""Tests for validated filters and parameterized pitch-search SQL."""

from __future__ import annotations

from app.routers import pitches as pitch_routes
from app.schemas.filters import PitchFilters, PitchSortField, SortOrder


def test_combined_filters_are_passed_as_sql_parameters(
    monkeypatch, scripted_connection_factory
) -> None:
    row = {
        "pitch_id": "824566_10_5",
        "pitch_type": "SL",
        "balls": 1,
        "strikes": 2,
        "batter_side": "R",
    }
    connection = scripted_connection_factory([{"total_matches": 1}, [row]])
    monkeypatch.setattr(
        pitch_routes,
        "require_pitcher",
        lambda _connection, _pitcher_id: {"player_id": 7},
    )
    filters = PitchFilters(
        pitcher_id=7,
        season=2026,
        team_id=12,
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
    assert "g.season = %s" in call.query
    assert "g.home_team_id" in call.query
    assert "p.balls = %s" in call.query
    assert "p.strikes = %s" in call.query
    assert "COALESCE(v.video_available, FALSE) = %s" in call.query
    assert "swinging_strike" not in call.query
    assert call.parameters == [
        7,
        2026,
        12,
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
    assert "ORDER BY g.game_date ASC NULLS LAST" in call.query


def test_lowercase_filter_codes_are_normalized() -> None:
    filters = PitchFilters(
        pitch_type="ff",
        batter_side="l",
        sort_by="VELOCITY",
        sort_order="DESC",
    )

    assert filters.pitch_type.value == "FF"
    assert filters.batter_side.value == "L"
    assert filters.sort_by is PitchSortField.VELOCITY
    assert filters.sort_order is SortOrder.DESCENDING


def test_server_side_sorting_uses_only_allowlisted_sql(
    monkeypatch, scripted_connection_factory
) -> None:
    row = {
        "pitch_id": "824566_10_5",
        "velocity": 97.1,
    }
    connection = scripted_connection_factory([{"total_matches": 26}, [row]])
    monkeypatch.setattr(
        pitch_routes,
        "require_pitcher",
        lambda _connection, _pitcher_id: {"player_id": 7},
    )

    response = pitch_routes.search_pitches(
        PitchFilters(
            pitcher_id=7,
            limit=25,
            offset=25,
            sort_by="velocity",
            sort_order="desc",
        ),
        connection,
    )

    call = connection.calls[-1]
    assert "ORDER BY p.velocity DESC NULLS LAST" in call.query
    assert call.parameters == [7, 25, 25]
    assert response["sort_by"] == "velocity"
    assert response["sort_order"] == "desc"
    assert response["has_previous"] is True
    assert response["has_next"] is False


def test_empty_page_keeps_the_filtered_total(monkeypatch, scripted_connection_factory) -> None:
    connection = scripted_connection_factory([{"total_matches": 50}, []])
    monkeypatch.setattr(
        pitch_routes,
        "require_pitcher",
        lambda _connection, _pitcher_id: {"player_id": 7},
    )

    response = pitch_routes.search_pitches(
        PitchFilters(pitcher_id=7, limit=25, offset=50),
        connection,
    )

    assert response["total"] == 50
    assert response["pitches"] == []
    assert response["has_previous"] is True
    assert response["has_next"] is False


def test_invalid_sort_field_is_rejected() -> None:
    try:
        PitchFilters(sort_by="p.velocity; DROP TABLE pitches")
    except ValueError as error:
        assert "sort_by" in str(error)
    else:
        raise AssertionError("An unknown sort field should fail validation")
