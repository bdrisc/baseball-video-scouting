"""Season and team discovery routes for the scouting workspace."""

from typing import Annotated

import psycopg
from fastapi import APIRouter, Depends, Query

from app.database import get_db

router = APIRouter(tags=["catalog"])

PITCHER_TEAM_ID_SQL = """
    CASE
        WHEN LOWER(p.inning_half) = 'top' THEN g.home_team_id
        WHEN LOWER(p.inning_half) IN ('bot', 'bottom') THEN g.away_team_id
    END
"""


@router.get("/seasons")
def list_seasons(connection: psycopg.Connection = Depends(get_db)) -> list[dict]:
    """Return seasons that contain pitch data, newest first."""
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT
                g.season,
                COUNT(DISTINCT g.game_pk) AS game_count,
                COUNT(DISTINCT p.pitcher_id) AS pitcher_count,
                COUNT(p.pitch_id) AS pitch_count,
                MIN(g.game_date) AS first_game,
                MAX(g.game_date) AS last_game
            FROM games AS g
            JOIN pitches AS p ON p.game_pk = g.game_pk
            GROUP BY g.season
            ORDER BY g.season DESC
            """
        )
        return cursor.fetchall()


@router.get("/teams")
def list_teams(
    season: Annotated[int | None, Query(ge=1876, le=2200)] = None,
    connection: psycopg.Connection = Depends(get_db),
) -> list[dict]:
    """Return teams represented by pitches in the selected season."""
    conditions = ""
    parameters: list[object] = []
    if season is not None:
        conditions = " WHERE g.season = %s"
        parameters.append(season)

    query = (
        f"""
        SELECT
            t.team_id,
            t.team_code,
            COALESCE(t.team_name, t.team_code) AS team_name,
            COUNT(DISTINCT g.game_pk) AS game_count,
            COUNT(DISTINCT p.pitcher_id) AS pitcher_count,
            COUNT(p.pitch_id) AS pitch_count
        FROM teams AS t
        JOIN games AS g
          ON t.team_id IN (g.home_team_id, g.away_team_id)
        LEFT JOIN pitches AS p
          ON p.game_pk = g.game_pk
         AND ({PITCHER_TEAM_ID_SQL}) = t.team_id
        """
        + conditions
        + """
        GROUP BY t.team_id, t.team_code, t.team_name
        HAVING COUNT(p.pitch_id) > 0
        ORDER BY COALESCE(t.team_name, t.team_code), t.team_code
        """
    )
    with connection.cursor() as cursor:
        cursor.execute(query, parameters)
        return cursor.fetchall()
