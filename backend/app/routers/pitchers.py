"""Pitcher list, game list, and summary routes."""

from typing import Annotated

import psycopg
from fastapi import APIRouter, Depends, Path

from app.database import get_db
from app.services.validation import require_pitcher

router = APIRouter(prefix="/pitchers", tags=["pitchers"])


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


@router.get("/{pitcher_id}/games")
def list_pitcher_games(
    pitcher_id: Annotated[int, Path(gt=0)],
    connection: psycopg.Connection = Depends(get_db),
) -> dict:
    pitcher = require_pitcher(connection, pitcher_id)

    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT
                g.game_pk,
                g.game_date,
                g.home_team,
                g.away_team,
                COUNT(p.pitch_id) AS pitch_count,
                COUNT(*) FILTER (WHERE v.video_available IS TRUE) AS video_count
            FROM games AS g
            JOIN pitches AS p ON p.game_pk = g.game_pk
            LEFT JOIN videos AS v ON v.pitch_id = p.pitch_id
            WHERE p.pitcher_id = %s
            GROUP BY g.game_pk, g.game_date, g.home_team, g.away_team
            ORDER BY g.game_date, g.game_pk
            """,
            (pitcher_id,),
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
