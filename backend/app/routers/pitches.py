"""Pitch search, detail, and video routes."""

from typing import Annotated

import psycopg
from fastapi import APIRouter, Depends, HTTPException, Path, Query, status

from app.database import get_db
from app.schemas.common import PITCH_ID_PATTERN
from app.schemas.filters import PitchFilters
from app.services.validation import require_game, require_pitcher

router = APIRouter(prefix="/pitches", tags=["pitches"])


PITCH_SELECT = """
    SELECT
        p.*,
        pitcher.player_name AS pitcher_name,
        pitcher.mlb_id AS pitcher_mlb_id,
        batter.player_name AS batter_name,
        batter.mlb_id AS batter_mlb_id,
        g.game_date,
        g.home_team,
        g.away_team,
        v.video_id,
        v.video_url,
        v.video_type,
        COALESCE(v.video_available, FALSE) AS video_available,
        v.notes AS video_notes
    FROM pitches AS p
    JOIN players AS pitcher ON pitcher.player_id = p.pitcher_id
    LEFT JOIN players AS batter ON batter.player_id = p.batter_id
    JOIN games AS g ON g.game_pk = p.game_pk
    LEFT JOIN videos AS v ON v.pitch_id = p.pitch_id
"""


@router.get("")
def search_pitches(
    filters: Annotated[PitchFilters, Query()],
    connection: psycopg.Connection = Depends(get_db),
) -> dict:
    """Return pitches matching any supplied combination of filters."""
    if filters.pitcher_id is not None:
        require_pitcher(connection, filters.pitcher_id)
    if filters.game_pk is not None:
        require_game(connection, filters.game_pk)

    conditions: list[str] = []
    parameters: list[object] = []

    sql_filters = (
        ("p.pitcher_id = %s", filters.pitcher_id),
        ("p.game_pk = %s", filters.game_pk),
        (
            "p.pitch_type = %s",
            filters.pitch_type.value if filters.pitch_type is not None else None,
        ),
        ("p.balls = %s", filters.balls),
        ("p.strikes = %s", filters.strikes),
        (
            "p.batter_side = %s",
            filters.batter_side.value if filters.batter_side is not None else None,
        ),
        ("g.game_date >= %s", filters.start_date),
        ("g.game_date <= %s", filters.end_date),
        ("p.velocity >= %s", filters.min_velocity),
        ("p.velocity <= %s", filters.max_velocity),
        ("p.plate_x >= %s", filters.min_plate_x),
        ("p.plate_x <= %s", filters.max_plate_x),
        ("p.plate_z >= %s", filters.min_plate_z),
        ("p.plate_z <= %s", filters.max_plate_z),
    )
    for sql_fragment, value in sql_filters:
        if value is not None:
            conditions.append(sql_fragment)
            parameters.append(value)

    if filters.result is not None:
        conditions.append("(p.description = %s OR p.events = %s)")
        parameters.extend((filters.result, filters.result))

    if filters.video_available is not None:
        conditions.append("COALESCE(v.video_available, FALSE) = %s")
        parameters.append(filters.video_available)

    where_clause = ""
    if conditions:
        where_clause = " WHERE " + " AND ".join(conditions)

    query = (
        PITCH_SELECT.replace(
            "SELECT\n        p.*",
            "SELECT\n        COUNT(*) OVER () AS total_matches,\n        p.*",
            1,
        )
        + where_clause
        + " ORDER BY g.game_date, p.game_pk, p.at_bat_number, p.pitch_number"
        + " LIMIT %s OFFSET %s"
    )
    parameters.extend((filters.limit, filters.offset))

    with connection.cursor() as cursor:
        cursor.execute(query, parameters)
        rows = cursor.fetchall()

    total = rows[0]["total_matches"] if rows else 0
    for row in rows:
        row.pop("total_matches", None)

    return {
        "total": total,
        "limit": filters.limit,
        "offset": filters.offset,
        "pitches": rows,
    }


@router.get("/{pitch_id}")
def get_pitch(
    pitch_id: Annotated[
        str,
        Path(
            min_length=5,
            max_length=100,
            pattern=PITCH_ID_PATTERN,
            description="Pitch ID formatted as gamePk_atBatNumber_pitchNumber",
        ),
    ],
    connection: psycopg.Connection = Depends(get_db),
) -> dict:
    with connection.cursor() as cursor:
        cursor.execute(PITCH_SELECT + " WHERE p.pitch_id = %s", (pitch_id,))
        pitch = cursor.fetchone()

    if pitch is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Pitch {pitch_id} was not found.",
        )
    return pitch


@router.get("/{pitch_id}/video")
def get_pitch_video(
    pitch_id: Annotated[
        str,
        Path(
            min_length=5,
            max_length=100,
            pattern=PITCH_ID_PATTERN,
            description="Pitch ID formatted as gamePk_atBatNumber_pitchNumber",
        ),
    ],
    connection: psycopg.Connection = Depends(get_db),
) -> dict:
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT
                p.pitch_id,
                v.video_id,
                v.video_url,
                v.video_type,
                COALESCE(v.video_available, FALSE) AS video_available,
                v.notes
            FROM pitches AS p
            LEFT JOIN videos AS v ON v.pitch_id = p.pitch_id
            WHERE p.pitch_id = %s
            """,
            (pitch_id,),
        )
        video = cursor.fetchone()

    if video is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Pitch {pitch_id} was not found.",
        )
    return video
