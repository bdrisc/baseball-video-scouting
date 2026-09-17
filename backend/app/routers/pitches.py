"""Pitch search, aggregate, detail, and video routes."""

from collections.abc import Callable
from typing import Annotated

import psycopg
from fastapi import APIRouter, Depends, HTTPException, Path, Query, status

from app.database import get_db
from app.schemas.common import PITCH_ID_PATTERN
from app.schemas.filters import (
    PitchAggregateFilters,
    PitchFilterCriteria,
    PitchFilters,
    PitchSortField,
)
from app.services.validation import require_game, require_pitcher

router = APIRouter(prefix="/pitches", tags=["pitches"])


PITCH_FROM = """
    FROM pitches AS p
    JOIN players AS pitcher ON pitcher.player_id = p.pitcher_id
    LEFT JOIN players AS batter ON batter.player_id = p.batter_id
    JOIN games AS g ON g.game_pk = p.game_pk
    LEFT JOIN videos AS v ON v.pitch_id = p.pitch_id
"""

AGGREGATE_FROM = """
    FROM pitches AS p
    JOIN games AS g ON g.game_pk = p.game_pk
    LEFT JOIN videos AS v ON v.pitch_id = p.pitch_id
"""

PITCH_SELECT = (
    """
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
"""
    + PITCH_FROM
)

PITCH_SORT_COLUMNS = {
    PitchSortField.GAME_DATE: "g.game_date",
    PitchSortField.BATTER_NAME: "batter.player_name",
    PitchSortField.PITCH_TYPE: "p.pitch_type",
    PitchSortField.VELOCITY: "p.velocity",
    PitchSortField.SPIN_RATE: "p.spin_rate",
    PitchSortField.INNING: "p.inning",
    PitchSortField.RESULT: "COALESCE(p.events, p.description)",
}

WHIFF_DESCRIPTIONS = (
    "swinging_strike",
    "swinging_strike_blocked",
    "missed_bunt",
)
SWING_DESCRIPTIONS = (
    *WHIFF_DESCRIPTIONS,
    "foul",
    "foul_tip",
    "foul_bunt",
    "bunt_foul_tip",
    "hit_into_play",
    "hit_into_play_no_out",
    "hit_into_play_score",
)

PITCHER_TEAM_ID_SQL = """
    CASE
        WHEN LOWER(p.inning_half) = 'top' THEN g.home_team_id
        WHEN LOWER(p.inning_half) IN ('bot', 'bottom') THEN g.away_team_id
    END
"""


def _build_pitch_where(filters: PitchFilterCriteria) -> tuple[str, list[object]]:
    """Build one parameterized WHERE clause shared by rows and aggregates."""
    conditions: list[str] = []
    parameters: list[object] = []

    sql_filters = (
        ("p.pitcher_id = %s", filters.pitcher_id),
        ("p.game_pk = %s", filters.game_pk),
        ("g.season = %s", filters.season),
        (f"({PITCHER_TEAM_ID_SQL}) = %s", filters.team_id),
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
    return where_clause, parameters


def _rate(numerator: int, denominator: int) -> float | None:
    return 100.0 * numerator / denominator if denominator else None


def _top_pitch(rows: list[dict]) -> tuple[str, float | None, int]:
    if not rows:
        return "—", None, 0
    counts: dict[str, int] = {}
    for row in rows:
        pitch_type = row["pitch_type"]
        counts[pitch_type] = counts.get(pitch_type, 0) + row["pitch_count"]
    pitch_type, count = sorted(counts.items(), key=lambda item: (-item[1], item[0]))[0]
    sample_size = sum(counts.values())
    return pitch_type, _rate(count, sample_size), sample_size


def _most_common(rows: list[dict], field: str) -> str:
    counts: dict[str, int] = {}
    for row in rows:
        value = row[field]
        counts[value] = counts.get(value, 0) + row["pitch_count"]
    if not counts:
        return "—"
    return sorted(counts.items(), key=lambda item: (-item[1], item[0]))[0][0]


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

    where_clause, parameters = _build_pitch_where(filters)

    sort_column = PITCH_SORT_COLUMNS[filters.sort_by]
    sort_order = filters.sort_order.value.upper()
    tie_order = sort_order if filters.sort_by is PitchSortField.GAME_DATE else "DESC"
    order_clause = (
        f" ORDER BY {sort_column} {sort_order} NULLS LAST,"
        f" g.game_date {tie_order}, p.game_pk {tie_order},"
        f" p.at_bat_number {tie_order}, p.pitch_number {tie_order},"
        f" p.pitch_id {tie_order}"
    )
    count_query = "SELECT COUNT(*) AS total_matches" + PITCH_FROM + where_clause
    page_query = PITCH_SELECT + where_clause + order_clause + " LIMIT %s OFFSET %s"
    page_parameters = [*parameters, filters.limit, filters.offset]

    with connection.cursor() as cursor:
        cursor.execute(count_query, parameters)
        count_row = cursor.fetchone()
        cursor.execute(page_query, page_parameters)
        rows = cursor.fetchall()

    total = count_row["total_matches"] if count_row else 0

    return {
        "total": total,
        "limit": filters.limit,
        "offset": filters.offset,
        "sort_by": filters.sort_by.value,
        "sort_order": filters.sort_order.value,
        "has_previous": filters.offset > 0,
        "has_next": filters.offset + len(rows) < total,
        "pitches": rows,
    }


@router.get("/aggregates")
def pitch_aggregates(
    filters: Annotated[PitchAggregateFilters, Query()],
    connection: psycopg.Connection = Depends(get_db),
) -> dict:
    """Summarize the complete filtered result independently of pagination."""
    if filters.pitcher_id is not None:
        require_pitcher(connection, filters.pitcher_id)
    if filters.game_pk is not None:
        require_game(connection, filters.game_pk)

    where_clause, parameters = _build_pitch_where(filters)
    swing_placeholders = ", ".join(["%s"] * len(SWING_DESCRIPTIONS))
    whiff_placeholders = ", ".join(["%s"] * len(WHIFF_DESCRIPTIONS))
    metric_parameters = [*SWING_DESCRIPTIONS, *WHIFF_DESCRIPTIONS, *parameters]

    summary_query = (
        f"""
        SELECT
            COUNT(*) AS total_pitches,
            AVG(p.velocity) AS average_velocity,
            COUNT(*) FILTER (
                WHERE p.description IN ({whiff_placeholders})
            ) AS whiffs,
            COUNT(*) FILTER (
                WHERE COALESCE(v.video_available, FALSE)
            ) AS videos_available,
            COUNT(DISTINCT COALESCE(p.pitch_type, 'unknown')) AS pitch_types
        """
        + AGGREGATE_FROM
        + where_clause
    )
    summary_parameters = [*WHIFF_DESCRIPTIONS, *parameters]

    arsenal_query = (
        f"""
        SELECT
            COALESCE(p.pitch_type, 'unknown') AS pitch_type,
            COUNT(*) AS pitch_count,
            AVG(p.velocity) AS average_velocity,
            AVG(p.spin_rate) AS average_spin,
            AVG(p.horizontal_break) AS horizontal_break,
            AVG(p.vertical_break) AS vertical_break,
            COUNT(*) FILTER (
                WHERE p.description IN ({swing_placeholders})
                   OR p.description LIKE 'in_play%%'
            ) AS swing_count,
            COUNT(*) FILTER (
                WHERE p.description IN ({whiff_placeholders})
            ) AS whiff_count,
            COUNT(*) FILTER (
                WHERE p.plate_x IS NOT NULL AND p.plate_z IS NOT NULL
            ) AS located_count,
            COUNT(*) FILTER (
                WHERE p.plate_x BETWEEN -0.83 AND 0.83
                  AND p.plate_z BETWEEN 1.5 AND 3.5
            ) AS zone_count,
            COUNT(p.exit_velocity) AS balls_in_play,
            AVG(p.exit_velocity) AS average_exit_velocity,
            MAX(p.exit_velocity) AS maximum_exit_velocity,
            COUNT(*) FILTER (WHERE p.exit_velocity >= 95) AS hard_hits,
            COUNT(*) FILTER (WHERE p.events = 'home_run') AS home_runs
        """
        + AGGREGATE_FROM
        + where_clause
        + " GROUP BY COALESCE(p.pitch_type, 'unknown')"
        + " ORDER BY pitch_count DESC, pitch_type"
    )

    velocity_query = (
        """
        SELECT
            COALESCE(p.pitch_type, 'unknown') AS pitch_type,
            p.inning,
            COUNT(*) AS pitch_count,
            AVG(p.velocity) AS average_velocity
        """
        + AGGREGATE_FROM
        + where_clause
        + (
            " AND p.inning IS NOT NULL AND p.velocity IS NOT NULL"
            if where_clause
            else " WHERE p.inning IS NOT NULL AND p.velocity IS NOT NULL"
        )
    )
    velocity_query += (
        " GROUP BY COALESCE(p.pitch_type, 'unknown'), p.inning ORDER BY pitch_type, p.inning"
    )

    count_query = (
        f"""
        SELECT
            COALESCE(p.pitch_type, 'unknown') AS pitch_type,
            p.balls,
            p.strikes,
            COUNT(*) AS pitch_count,
            COUNT(*) FILTER (
                WHERE p.description IN ({swing_placeholders})
                   OR p.description LIKE 'in_play%%'
            ) AS swing_count,
            COUNT(*) FILTER (
                WHERE p.description IN ({whiff_placeholders})
            ) AS whiff_count,
            COUNT(*) FILTER (
                WHERE p.events IN ('strikeout', 'strikeout_double_play')
            ) AS strikeout_count
        """
        + AGGREGATE_FROM
        + where_clause
        + " GROUP BY COALESCE(p.pitch_type, 'unknown'), p.balls, p.strikes"
        + " ORDER BY p.balls, p.strikes, pitch_count DESC, pitch_type"
    )

    results_query = (
        f"""
        SELECT
            p.batter_side,
            CASE
                WHEN p.description IN ({whiff_placeholders}) THEN 'Whiff'
                WHEN p.description = 'called_strike' THEN 'Called strike'
                WHEN p.description LIKE '%%foul%%' THEN 'Foul'
                WHEN p.description LIKE 'hit_into_play%%'
                  OR p.description LIKE 'in_play%%' THEN 'In play'
                WHEN p.description IN ('ball', 'blocked_ball', 'pitchout')
                    THEN 'Ball'
                ELSE 'Other'
            END AS result_group,
            COUNT(*) AS pitch_count
        """
        + AGGREGATE_FROM
        + where_clause
        + (
            " AND p.batter_side IN ('L', 'R')"
            if where_clause
            else " WHERE p.batter_side IN ('L', 'R')"
        )
        + " GROUP BY p.batter_side, result_group"
        + " ORDER BY p.batter_side, result_group"
    )
    results_parameters = [*WHIFF_DESCRIPTIONS, *parameters]

    handedness_query = (
        f"""
        SELECT
            p.batter_side,
            COALESCE(p.pitch_type, 'unknown') AS pitch_type,
            COUNT(*) AS pitch_count,
            COUNT(*) FILTER (
                WHERE p.description IN ({swing_placeholders})
                   OR p.description LIKE 'in_play%%'
            ) AS swing_count,
            COUNT(*) FILTER (
                WHERE p.description IN ({whiff_placeholders})
            ) AS whiff_count,
            COUNT(*) FILTER (
                WHERE p.plate_x IS NOT NULL AND p.plate_z IS NOT NULL
            ) AS located_count,
            COUNT(*) FILTER (
                WHERE p.plate_x BETWEEN -0.83 AND 0.83
                  AND p.plate_z BETWEEN 1.5 AND 3.5
            ) AS zone_count
        """
        + AGGREGATE_FROM
        + where_clause
        + (
            " AND p.batter_side IN ('L', 'R')"
            if where_clause
            else " WHERE p.batter_side IN ('L', 'R')"
        )
        + " GROUP BY p.batter_side, COALESCE(p.pitch_type, 'unknown')"
        + " ORDER BY p.batter_side, pitch_count DESC, pitch_type"
    )

    location_query = (
        """
        SELECT
            CASE
                WHEN p.plate_z > 3.5 THEN 'Above zone'
                WHEN p.plate_z >= 2.83 THEN 'Upper third'
                WHEN p.plate_z >= 2.17 THEN 'Middle third'
                WHEN p.plate_z >= 1.5 THEN 'Lower third'
                ELSE 'Below zone'
            END AS vertical_band,
            CASE
                WHEN p.plate_x < -0.83 THEN 'Left off plate'
                WHEN p.plate_x < -0.28 THEN 'Left third'
                WHEN p.plate_x <= 0.28 THEN 'Center third'
                WHEN p.plate_x <= 0.83 THEN 'Right third'
                ELSE 'Right off plate'
            END AS horizontal_lane,
            COUNT(*) AS pitch_count,
            COUNT(*) FILTER (
                WHERE p.plate_x BETWEEN -0.83 AND 0.83
                  AND p.plate_z BETWEEN 1.5 AND 3.5
            ) AS zone_count,
            COUNT(*) FILTER (
                WHERE COALESCE(p.pitch_type, 'unknown')
                    IN ('FF', 'FA', 'SI', 'FT', 'FC')
            ) AS fastball_count,
            COUNT(*) FILTER (
                WHERE COALESCE(p.pitch_type, 'unknown')
                    IN ('FF', 'FA', 'SI', 'FT', 'FC')
                  AND p.plate_z >= 2.83
            ) AS elevated_fastball_count
        """
        + AGGREGATE_FROM
        + where_clause
        + (
            " AND p.plate_x IS NOT NULL AND p.plate_z IS NOT NULL"
            if where_clause
            else " WHERE p.plate_x IS NOT NULL AND p.plate_z IS NOT NULL"
        )
        + " GROUP BY vertical_band, horizontal_lane"
        + " ORDER BY vertical_band, horizontal_lane"
    )

    queries: list[tuple[str, list[object]]] = [
        (summary_query, summary_parameters),
        (arsenal_query, metric_parameters),
        (velocity_query, parameters),
        (count_query, metric_parameters),
        (results_query, results_parameters),
        (handedness_query, metric_parameters),
        (location_query, parameters),
    ]
    responses: list[object] = []
    with connection.cursor() as cursor:
        for query, query_parameters in queries:
            cursor.execute(query, query_parameters)
            responses.append(cursor.fetchall())

    (
        summary_rows,
        arsenal_rows,
        velocity_rows,
        count_rows,
        result_rows,
        handedness_rows,
        location_rows,
    ) = responses
    summary = (
        summary_rows[0]
        if summary_rows
        else {
            "total_pitches": 0,
            "average_velocity": None,
            "whiffs": 0,
            "videos_available": 0,
            "pitch_types": 0,
        }
    )
    total_pitches = summary["total_pitches"]

    pitch_usage = [
        {
            "pitch_type": row["pitch_type"],
            "pitch_count": row["pitch_count"],
            "usage_percent": _rate(row["pitch_count"], total_pitches) or 0.0,
        }
        for row in arsenal_rows
    ]

    count_totals: dict[tuple[int, int], int] = {}
    for row in count_rows:
        key = (row["balls"], row["strikes"])
        count_totals[key] = count_totals.get(key, 0) + row["pitch_count"]
    usage_by_count = [
        {
            "pitch_type": row["pitch_type"],
            "balls": row["balls"],
            "strikes": row["strikes"],
            "pitch_count": row["pitch_count"],
            "usage_percent": _rate(row["pitch_count"], count_totals[(row["balls"], row["strikes"])])
            or 0.0,
        }
        for row in count_rows
    ]

    side_totals: dict[str, int] = {}
    for row in result_rows:
        side = row["batter_side"]
        side_totals[side] = side_totals.get(side, 0) + row["pitch_count"]
    results_by_batter_side = [
        {
            **row,
            "percentage": _rate(row["pitch_count"], side_totals[row["batter_side"]]) or 0.0,
        }
        for row in result_rows
    ]

    arsenal = [
        {
            "pitch_type": row["pitch_type"],
            "count": row["pitch_count"],
            "usage": _rate(row["pitch_count"], total_pitches) or 0.0,
            "average_velocity": row["average_velocity"],
            "average_spin": row["average_spin"],
            "horizontal_break": row["horizontal_break"],
            "vertical_break": row["vertical_break"],
            "whiff_rate": _rate(row["whiff_count"], row["swing_count"]),
            "zone_rate": _rate(row["zone_count"], row["located_count"]),
        }
        for row in arsenal_rows
    ]
    usage_summary = (
        " · ".join(f"{row['pitch_type']} {row['usage']:.1f}%" for row in arsenal)
        if arsenal
        else "—"
    )

    count_groups: list[tuple[str, Callable[[dict], bool]]] = [
        ("First pitch", lambda row: row["balls"] == 0 and row["strikes"] == 0),
        ("Pitcher ahead", lambda row: row["strikes"] > row["balls"]),
        ("Hitter ahead", lambda row: row["balls"] > row["strikes"]),
        ("Two strikes", lambda row: row["strikes"] == 2),
        ("Full count", lambda row: row["balls"] == 3 and row["strikes"] == 2),
    ]
    count_tendencies = []
    for label, include in count_groups:
        pitch_type, usage, sample_size = _top_pitch([row for row in count_rows if include(row)])
        count_tendencies.append(
            {
                "label": label,
                "sample_size": sample_size,
                "top_pitch": pitch_type,
                "usage": usage,
            }
        )

    handedness = []
    for side in ("L", "R"):
        rows = [row for row in handedness_rows if row["batter_side"] == side]
        side_count = sum(row["pitch_count"] for row in rows)
        swings = sum(row["swing_count"] for row in rows)
        whiffs = sum(row["whiff_count"] for row in rows)
        located = sum(row["located_count"] for row in rows)
        zones = sum(row["zone_count"] for row in rows)
        handedness.append(
            {
                "side": side,
                "count": side_count,
                "pitch_mix": [
                    {
                        "pitch_type": row["pitch_type"],
                        "usage": _rate(row["pitch_count"], side_count) or 0.0,
                    }
                    for row in rows
                ],
                "whiff_rate": _rate(whiffs, swings),
                "zone_rate": _rate(zones, located),
            }
        )

    located_count = sum(row["pitch_count"] for row in location_rows)
    zone_count = sum(row["zone_count"] for row in location_rows)
    fastball_count = sum(row["fastball_count"] for row in location_rows)
    elevated_fastballs = sum(row["elevated_fastball_count"] for row in location_rows)

    two_strike_rows = [row for row in count_rows if row["strikes"] == 2]
    two_strike_pitch, two_strike_usage, two_strike_sample = _top_pitch(two_strike_rows)
    two_strike_swings = sum(row["swing_count"] for row in two_strike_rows)
    two_strike_whiffs = sum(row["whiff_count"] for row in two_strike_rows)
    whiff_pitch_rows = [row for row in two_strike_rows if row["whiff_count"] > 0]
    whiff_pitch_rows.sort(
        key=lambda row: (
            -((row["whiff_count"] / row["swing_count"]) if row["swing_count"] else -1),
            -row["whiff_count"],
            row["pitch_type"],
        )
    )

    balls_in_play = sum(row["balls_in_play"] for row in arsenal_rows)
    hard_hits = sum(row["hard_hits"] for row in arsenal_rows)
    weighted_exit_velocity = sum(
        (row["average_exit_velocity"] or 0) * row["balls_in_play"] for row in arsenal_rows
    )
    damage_rows = [row for row in arsenal_rows if row["balls_in_play"]]
    damage_rows.sort(
        key=lambda row: (
            -(row["average_exit_velocity"] or 0),
            -row["balls_in_play"],
            row["pitch_type"],
        )
    )

    report = {
        "arsenal": arsenal,
        "usage_summary": usage_summary,
        "count_tendencies": count_tendencies,
        "handedness": handedness,
        "location": {
            "sample_size": located_count,
            "zone_rate": _rate(zone_count, located_count),
            "primary_vertical_band": _most_common(location_rows, "vertical_band"),
            "primary_horizontal_lane": _most_common(location_rows, "horizontal_lane"),
            "fastball_elevated_rate": _rate(elevated_fastballs, fastball_count),
        },
        "putaway": {
            "sample_size": two_strike_sample,
            "top_pitch": two_strike_pitch,
            "top_pitch_usage": two_strike_usage,
            "whiff_rate": _rate(two_strike_whiffs, two_strike_swings),
            "strikeouts": sum(row["strikeout_count"] for row in two_strike_rows),
            "best_whiff_pitch": (whiff_pitch_rows[0]["pitch_type"] if whiff_pitch_rows else "—"),
        },
        "damage": {
            "balls_in_play": balls_in_play,
            "average_exit_velocity": (
                weighted_exit_velocity / balls_in_play if balls_in_play else None
            ),
            "hard_hit_rate": _rate(hard_hits, balls_in_play),
            "maximum_exit_velocity": max(
                (
                    row["maximum_exit_velocity"]
                    for row in damage_rows
                    if row["maximum_exit_velocity"] is not None
                ),
                default=None,
            ),
            "home_runs": sum(row["home_runs"] for row in arsenal_rows),
            "most_damaged_pitch": (damage_rows[0]["pitch_type"] if damage_rows else "—"),
        },
    }

    return {
        "total": total_pitches,
        "summary": summary,
        "pitch_usage": pitch_usage,
        "velocity_by_inning": velocity_rows,
        "usage_by_count": usage_by_count,
        "results_by_batter_side": results_by_batter_side,
        "report": report,
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
