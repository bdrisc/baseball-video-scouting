"""Pitcher list, game list, and summary routes."""

from typing import Annotated

import psycopg
from fastapi import APIRouter, Depends, Path, Query

from app.database import get_db
from app.schemas.filters import PitcherSearchFilters
from app.services.validation import require_pitcher

router = APIRouter(prefix="/pitchers", tags=["pitchers"])

PITCHER_TEAM_ID_SQL = """
    CASE
        WHEN LOWER(p.inning_half) = 'top' THEN g.home_team_id
        WHEN LOWER(p.inning_half) IN ('bot', 'bottom') THEN g.away_team_id
    END
"""


@router.get("")
def list_pitchers(connection: psycopg.Connection = Depends(get_db)) -> list[dict]:
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT
                pl.player_id,
                pl.mlb_id,
                pl.player_name,
                pl.throws,
                COUNT(p.pitch_id) AS pitch_count,
                COUNT(DISTINCT p.game_pk) AS game_count,
                MIN(g.game_date) AS first_game,
                MAX(g.game_date) AS last_game
            FROM players AS pl
            JOIN pitches AS p ON p.pitcher_id = pl.player_id
            JOIN games AS g ON g.game_pk = p.game_pk
            GROUP BY pl.player_id, pl.mlb_id, pl.player_name, pl.throws
            ORDER BY pl.player_name
            """
        )
        return cursor.fetchall()


@router.get("/search")
def search_pitchers(
    filters: Annotated[PitcherSearchFilters, Query()],
    connection: psycopg.Connection = Depends(get_db),
) -> dict:
    """Search and paginate pitchers without loading a full-season roster."""
    conditions: list[str] = []
    parameters: list[object] = []

    if filters.q is not None:
        conditions.append("LOWER(COALESCE(pl.player_name, '')) LIKE '%%' || LOWER(%s) || '%%'")
        parameters.append(filters.q)
    if filters.season is not None:
        conditions.append("g.season = %s")
        parameters.append(filters.season)
    if filters.team_id is not None:
        conditions.append(f"({PITCHER_TEAM_ID_SQL}) = %s")
        parameters.append(filters.team_id)
    if filters.throws is not None:
        conditions.append("pl.throws = %s")
        parameters.append(filters.throws.value)

    where_clause = " WHERE " + " AND ".join(conditions) if conditions else ""
    search_from = f"""
        FROM players AS pl
        JOIN pitches AS p ON p.pitcher_id = pl.player_id
        JOIN games AS g ON g.game_pk = p.game_pk
        LEFT JOIN teams AS t ON t.team_id = ({PITCHER_TEAM_ID_SQL})
    """
    count_query = (
        "SELECT COUNT(DISTINCT pl.player_id) AS total_matches" + search_from + where_clause
    )
    page_query = (
        """
        SELECT
            pl.player_id,
            pl.mlb_id,
            COALESCE(pl.player_name, pl.mlb_id::text) AS player_name,
            pl.throws,
            COUNT(p.pitch_id) AS pitch_count,
            COUNT(DISTINCT p.game_pk) AS game_count,
            MIN(g.game_date) AS first_game,
            MAX(g.game_date) AS last_game,
            ARRAY_AGG(DISTINCT t.team_code ORDER BY t.team_code)
                FILTER (WHERE t.team_code IS NOT NULL) AS team_codes
        """
        + search_from
        + where_clause
        + """
        GROUP BY pl.player_id, pl.mlb_id, pl.player_name, pl.throws
        ORDER BY COALESCE(pl.player_name, pl.mlb_id::text), pl.player_id
        LIMIT %s OFFSET %s
        """
    )

    with connection.cursor() as cursor:
        cursor.execute(count_query, parameters)
        count_row = cursor.fetchone()
        cursor.execute(page_query, [*parameters, filters.limit, filters.offset])
        rows = cursor.fetchall()

    total = count_row["total_matches"] if count_row else 0
    return {
        "total": total,
        "limit": filters.limit,
        "offset": filters.offset,
        "has_previous": filters.offset > 0,
        "has_next": filters.offset + len(rows) < total,
        "pitchers": rows,
    }


@router.get("/{pitcher_id}/games")
def list_pitcher_games(
    pitcher_id: Annotated[int, Path(gt=0)],
    season: Annotated[int | None, Query(ge=1876, le=2200)] = None,
    team_id: Annotated[int | None, Query(gt=0)] = None,
    connection: psycopg.Connection = Depends(get_db),
) -> dict:
    pitcher = require_pitcher(connection, pitcher_id)

    with connection.cursor() as cursor:
        conditions = ["p.pitcher_id = %s"]
        parameters: list[object] = [pitcher_id]
        if season is not None:
            conditions.append("g.season = %s")
            parameters.append(season)
        if team_id is not None:
            conditions.append(f"({PITCHER_TEAM_ID_SQL}) = %s")
            parameters.append(team_id)
        cursor.execute(
            """
            SELECT
                g.game_pk,
                g.game_date,
                g.season,
                g.home_team,
                g.away_team,
                t.team_code AS pitcher_team,
                COUNT(p.pitch_id) AS pitch_count,
                COUNT(*) FILTER (WHERE v.video_available IS TRUE) AS video_count
            FROM games AS g
            JOIN pitches AS p ON p.game_pk = g.game_pk
            LEFT JOIN videos AS v ON v.pitch_id = p.pitch_id
            LEFT JOIN teams AS t ON t.team_id = ("""
            + PITCHER_TEAM_ID_SQL
            + ") WHERE "
            + " AND ".join(conditions)
            + """
            GROUP BY g.game_pk, g.game_date, g.season, g.home_team, g.away_team,
                     t.team_code
            ORDER BY g.game_date, g.game_pk
            """,
            parameters,
        )
        games = cursor.fetchall()

    return {"pitcher": pitcher, "games": games}


@router.get("/{pitcher_id}/summary")
def pitcher_summary(
    pitcher_id: Annotated[int, Path(gt=0)],
    connection: psycopg.Connection = Depends(get_db),
) -> dict:
    pitcher = require_pitcher(connection, pitcher_id)

    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT
                COUNT(*) AS pitch_count,
                COUNT(DISTINCT p.game_pk) AS game_count,
                MIN(g.game_date) AS first_game,
                MAX(g.game_date) AS last_game,
                ROUND(AVG(p.velocity)::numeric, 1) AS average_velocity,
                COUNT(*) FILTER (
                    WHERE p.description IN (
                        'swinging_strike',
                        'swinging_strike_blocked',
                        'missed_bunt'
                    )
                ) AS whiffs,
                COUNT(*) FILTER (WHERE v.video_available IS TRUE) AS videos_available
            FROM pitches AS p
            JOIN games AS g ON g.game_pk = p.game_pk
            LEFT JOIN videos AS v ON v.pitch_id = p.pitch_id
            WHERE p.pitcher_id = %s
            """,
            (pitcher_id,),
        )
        totals = cursor.fetchone()

        cursor.execute(
            """
            SELECT
                p.pitch_type,
                COUNT(*) AS pitch_count,
                ROUND(
                    100.0 * COUNT(*) / SUM(COUNT(*)) OVER (),
                    1
                ) AS usage_percent,
                ROUND(AVG(p.velocity)::numeric, 1) AS average_velocity,
                ROUND(MAX(p.velocity)::numeric, 1) AS max_velocity,
                ROUND(AVG(p.spin_rate)::numeric, 0) AS average_spin_rate,
                ROUND(AVG(p.horizontal_break)::numeric, 1) AS average_horizontal_break,
                ROUND(AVG(p.vertical_break)::numeric, 1) AS average_vertical_break
            FROM pitches AS p
            WHERE p.pitcher_id = %s
            GROUP BY p.pitch_type
            ORDER BY pitch_count DESC, p.pitch_type
            """,
            (pitcher_id,),
        )
        arsenal = cursor.fetchall()

    return {"pitcher": pitcher, "totals": totals, "arsenal": arsenal}
