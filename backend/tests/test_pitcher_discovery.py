"""Tests for season, team, and pitcher-discovery API queries."""

from __future__ import annotations

from app.routers import catalog
from app.routers import pitchers as pitcher_routes
from app.schemas.filters import PitcherSearchFilters


def test_pitcher_search_is_parameterized_and_paginated(
    scripted_connection_factory,
) -> None:
    pitcher = {
        "player_id": 7,
        "player_name": "Messick, Parker",
        "throws": "L",
        "pitch_count": 496,
        "team_codes": ["CLE"],
    }
    connection = scripted_connection_factory([{"total_matches": 1}, [pitcher]])

    response = pitcher_routes.search_pitchers(
        PitcherSearchFilters(
            q="messick",
            season=2026,
            team_id=12,
            throws="l",
            limit=25,
            offset=0,
        ),
        connection,
    )

    count_call, page_call = connection.calls
    assert "messick" not in count_call.query.lower()
    assert "g.season = %s" in page_call.query
    assert "g.home_team_id" in page_call.query
    assert page_call.parameters == ["messick", 2026, 12, "L", 25, 0]
    assert response["total"] == 1
    assert response["pitchers"] == [pitcher]
    assert response["has_next"] is False


def test_pitcher_search_reports_additional_pages(scripted_connection_factory) -> None:
    connection = scripted_connection_factory([{"total_matches": 80}, [{"player_id": 1}]])

    response = pitcher_routes.search_pitchers(
        PitcherSearchFilters(season=2026, limit=25, offset=25),
        connection,
    )

    assert response["has_previous"] is True
    assert response["has_next"] is True


def test_catalog_returns_database_rows(scripted_connection_factory) -> None:
    season_rows = [{"season": 2026, "pitch_count": 25000}]
    team_rows = [{"team_id": 12, "team_code": "CLE", "pitch_count": 1300}]

    season_connection = scripted_connection_factory([season_rows])
    team_connection = scripted_connection_factory([team_rows])

    assert catalog.list_seasons(season_connection) == season_rows
    assert catalog.list_teams(2026, team_connection) == team_rows
    assert team_connection.calls[0].parameters == [2026]
    assert "g.season = %s" in team_connection.calls[0].query
