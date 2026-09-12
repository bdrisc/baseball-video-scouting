#!/usr/bin/env python3
"""Load a cleaned Baseball Savant pitch dataset into PostgreSQL.

This loader is intentionally SQL-forward: pandas reads and validates the CSV,
while explicit PostgreSQL INSERT, SELECT, JOIN, GROUP BY, primary-key, and
foreign-key operations handle persistence and verification.

The script is safe to rerun. Existing rows are updated through ON CONFLICT
instead of being duplicated.
"""

from __future__ import annotations

import argparse
import getpass
import os
import sys
from pathlib import Path
from typing import Any

import pandas as pd
import psycopg

EXPECTED_TABLES = {
    "players",
    "games",
    "pitches",
    "videos",
    "playlists",
    "playlist_items",
}

REQUIRED_CSV_COLUMNS = {
    "pitch_id",
    "game_pk",
    "game_date",
    "home_team",
    "away_team",
    "player_name",
    "pitcher",
    "batter",
    "p_throws",
    "stand",
    "at_bat_number",
    "pitch_number",
    "inning",
    "inning_topbot",
    "pitch_type",
    "release_speed",
    "release_spin_rate",
    "pfx_x",
    "pfx_z",
    "release_extension",
    "plate_x",
    "plate_z",
    "balls",
    "strikes",
    "description",
    "events",
    "launch_speed",
    "launch_angle",
    "has_video",
    "video_url",
    "video_level",
    "video_notes",
}

OPTIONAL_CSV_COLUMNS = {
    "game_type",
    "outs_when_up",
    "pitch_name",
    "effective_speed",
    "release_pos_x",
    "release_pos_y",
    "release_pos_z",
    "sz_top",
    "sz_bot",
    "arm_angle",
    "zone",
    "bb_type",
    "is_strike",
    "is_swing",
    "is_contact",
    "is_whiff",
    "is_csw",
    "is_in_zone",
    "is_chase",
    "times_through_order",
    "hit_distance_sc",
    "estimated_ba_using_speedangle",
    "estimated_woba_using_speedangle",
    "woba_value",
    "delta_run_exp",
    "bat_speed",
    "swing_length",
    "is_hard_hit",
    "home_score",
    "away_score",
    "bat_score",
    "fld_score",
}

PLAYER_UPSERT_SQL = """
    INSERT INTO players (mlb_id, player_name, throws, bats)
    VALUES (%(mlb_id)s, %(player_name)s, %(throws)s, %(bats)s)
    ON CONFLICT (mlb_id) DO UPDATE
    SET
        player_name = COALESCE(EXCLUDED.player_name, players.player_name),
        throws = COALESCE(EXCLUDED.throws, players.throws),
        bats = COALESCE(EXCLUDED.bats, players.bats)
"""

GAME_UPSERT_SQL = """
    INSERT INTO games (game_pk, game_date, game_type, home_team, away_team)
    VALUES (%(game_pk)s, %(game_date)s, %(game_type)s, %(home_team)s, %(away_team)s)
    ON CONFLICT (game_pk) DO UPDATE
    SET
        game_date = EXCLUDED.game_date,
        game_type = EXCLUDED.game_type,
        home_team = EXCLUDED.home_team,
        away_team = EXCLUDED.away_team
"""

PITCH_UPSERT_SQL = """
    INSERT INTO pitches (
        pitch_id,
        game_pk,
        pitcher_id,
        batter_id,
        at_bat_number,
        pitch_number,
        inning,
        inning_half,
        outs_when_up,
        batter_side,
        pitch_type,
        pitch_name,
        velocity,
        effective_velocity,
        spin_rate,
        horizontal_break,
        vertical_break,
        release_extension,
        release_pos_x,
        release_pos_y,
        release_pos_z,
        plate_x,
        plate_z,
        strike_zone_top,
        strike_zone_bottom,
        arm_angle,
        zone,
        balls,
        strikes,
        description,
        events,
        batted_ball_type,
        is_strike,
        is_swing,
        is_contact,
        is_whiff,
        is_csw,
        is_in_zone,
        is_chase,
        times_through_order,
        exit_velocity,
        launch_angle,
        hit_distance,
        estimated_ba,
        estimated_woba,
        woba_value,
        delta_run_expectancy,
        bat_speed,
        swing_length,
        is_hard_hit,
        home_score,
        away_score,
        batter_score,
        fielding_score
    )
    VALUES (
        %(pitch_id)s,
        %(game_pk)s,
        %(pitcher_id)s,
        %(batter_id)s,
        %(at_bat_number)s,
        %(pitch_number)s,
        %(inning)s,
        %(inning_half)s,
        %(outs_when_up)s,
        %(batter_side)s,
        %(pitch_type)s,
        %(pitch_name)s,
        %(velocity)s,
        %(effective_velocity)s,
        %(spin_rate)s,
        %(horizontal_break)s,
        %(vertical_break)s,
        %(release_extension)s,
        %(release_pos_x)s,
        %(release_pos_y)s,
        %(release_pos_z)s,
        %(plate_x)s,
        %(plate_z)s,
        %(strike_zone_top)s,
        %(strike_zone_bottom)s,
        %(arm_angle)s,
        %(zone)s,
        %(balls)s,
        %(strikes)s,
        %(description)s,
        %(events)s,
        %(batted_ball_type)s,
        %(is_strike)s,
        %(is_swing)s,
        %(is_contact)s,
        %(is_whiff)s,
        %(is_csw)s,
        %(is_in_zone)s,
        %(is_chase)s,
        %(times_through_order)s,
        %(exit_velocity)s,
        %(launch_angle)s,
        %(hit_distance)s,
        %(estimated_ba)s,
        %(estimated_woba)s,
        %(woba_value)s,
        %(delta_run_expectancy)s,
        %(bat_speed)s,
        %(swing_length)s,
        %(is_hard_hit)s,
        %(home_score)s,
        %(away_score)s,
        %(batter_score)s,
        %(fielding_score)s
    )
    ON CONFLICT (pitch_id) DO UPDATE
    SET
        game_pk = EXCLUDED.game_pk,
        pitcher_id = EXCLUDED.pitcher_id,
        batter_id = EXCLUDED.batter_id,
        at_bat_number = EXCLUDED.at_bat_number,
        pitch_number = EXCLUDED.pitch_number,
        inning = EXCLUDED.inning,
        inning_half = EXCLUDED.inning_half,
        outs_when_up = EXCLUDED.outs_when_up,
        batter_side = EXCLUDED.batter_side,
        pitch_type = EXCLUDED.pitch_type,
        pitch_name = EXCLUDED.pitch_name,
        velocity = EXCLUDED.velocity,
        effective_velocity = EXCLUDED.effective_velocity,
        spin_rate = EXCLUDED.spin_rate,
        horizontal_break = EXCLUDED.horizontal_break,
        vertical_break = EXCLUDED.vertical_break,
        release_extension = EXCLUDED.release_extension,
        release_pos_x = EXCLUDED.release_pos_x,
        release_pos_y = EXCLUDED.release_pos_y,
        release_pos_z = EXCLUDED.release_pos_z,
        plate_x = EXCLUDED.plate_x,
        plate_z = EXCLUDED.plate_z,
        strike_zone_top = EXCLUDED.strike_zone_top,
        strike_zone_bottom = EXCLUDED.strike_zone_bottom,
        arm_angle = EXCLUDED.arm_angle,
        zone = EXCLUDED.zone,
        balls = EXCLUDED.balls,
        strikes = EXCLUDED.strikes,
        description = EXCLUDED.description,
        events = EXCLUDED.events,
        batted_ball_type = EXCLUDED.batted_ball_type,
        is_strike = EXCLUDED.is_strike,
        is_swing = EXCLUDED.is_swing,
        is_contact = EXCLUDED.is_contact,
        is_whiff = EXCLUDED.is_whiff,
        is_csw = EXCLUDED.is_csw,
        is_in_zone = EXCLUDED.is_in_zone,
        is_chase = EXCLUDED.is_chase,
        times_through_order = EXCLUDED.times_through_order,
        exit_velocity = EXCLUDED.exit_velocity,
        launch_angle = EXCLUDED.launch_angle,
        hit_distance = EXCLUDED.hit_distance,
        estimated_ba = EXCLUDED.estimated_ba,
        estimated_woba = EXCLUDED.estimated_woba,
        woba_value = EXCLUDED.woba_value,
        delta_run_expectancy = EXCLUDED.delta_run_expectancy,
        bat_speed = EXCLUDED.bat_speed,
        swing_length = EXCLUDED.swing_length,
        is_hard_hit = EXCLUDED.is_hard_hit,
        home_score = EXCLUDED.home_score,
        away_score = EXCLUDED.away_score,
        batter_score = EXCLUDED.batter_score,
        fielding_score = EXCLUDED.fielding_score
"""

VIDEO_UPSERT_SQL = """
    INSERT INTO videos (
        pitch_id,
        video_url,
        video_type,
        video_available,
        notes
    )
    VALUES (
        %(pitch_id)s,
        %(video_url)s,
        %(video_type)s,
        %(video_available)s,
        %(notes)s
    )
    ON CONFLICT (pitch_id) DO UPDATE
    SET
        video_url = EXCLUDED.video_url,
        video_type = EXCLUDED.video_type,
        video_available = EXCLUDED.video_available,
        notes = EXCLUDED.notes
"""


class LoaderError(ValueError):
    """Raised when the source data or database schema fails validation."""


def optional_text(value: Any, *, none_placeholder: bool = False) -> str | None:
    """Return stripped text or None for an unavailable value."""
    if pd.isna(value):
        return None
    text = str(value).strip()
    if not text or text.lower() == "nan":
        return None
    if none_placeholder and text.lower() == "none":
        return None
    return text


def optional_float(value: Any) -> float | None:
    """Convert a measurement to float while preserving missing values as NULL."""
    if pd.isna(value) or str(value).strip() == "":
        return None
    return float(value)


def optional_integer(value: Any) -> int | None:
    """Convert an integer-like value while preserving missing values as NULL."""
    number = optional_float(value)
    if number is None:
        return None
    if not number.is_integer():
        raise LoaderError(f"Expected an integer value, received {value!r}.")
    return int(number)


def parse_boolean(value: Any) -> bool:
    """Parse common CSV boolean representations."""
    if isinstance(value, bool):
        return value
    if pd.isna(value):
        return False
    normalized = str(value).strip().lower()
    if normalized in {"true", "1", "yes", "y"}:
        return True
    if normalized in {"false", "0", "no", "n", ""}:
        return False
    raise LoaderError(f"Cannot interpret boolean value: {value!r}")


def load_cleaned_csv(csv_path: Path) -> pd.DataFrame:
    """Read the cleaned CSV and validate its one-row-per-pitch grain."""
    if not csv_path.is_file():
        raise LoaderError(f"Cleaned CSV not found: {csv_path}")

    data = pd.read_csv(csv_path, low_memory=False)
    missing_columns = sorted(REQUIRED_CSV_COLUMNS - set(data.columns))
    if missing_columns:
        raise LoaderError("Cleaned CSV is missing required columns: " + ", ".join(missing_columns))

    for column in OPTIONAL_CSV_COLUMNS - set(data.columns):
        data[column] = pd.NA

    data["pitch_id"] = data["pitch_id"].astype("string").str.strip()
    if data["pitch_id"].isna().any() or data["pitch_id"].eq("").any():
        raise LoaderError("The cleaned CSV contains a missing pitch_id.")

    duplicate_mask = data["pitch_id"].duplicated(keep=False)
    if duplicate_mask.any():
        duplicate_ids = data.loc[duplicate_mask, "pitch_id"].drop_duplicates().head(10)
        raise LoaderError(
            f"Found {int(duplicate_mask.sum())} rows with duplicate pitch IDs. "
            "Examples: " + ", ".join(duplicate_ids)
        )

    integer_columns = [
        "game_pk",
        "pitcher",
        "batter",
        "at_bat_number",
        "pitch_number",
        "balls",
        "strikes",
    ]
    for column in integer_columns:
        numeric = pd.to_numeric(data[column], errors="coerce")
        if numeric.isna().any():
            raise LoaderError(
                f"Column {column!r} has {int(numeric.isna().sum())} invalid value(s)."
            )
        if numeric.mod(1).ne(0).any():
            raise LoaderError(f"Column {column!r} contains a non-integer value.")
        data[column] = numeric.astype("int64")

    parsed_dates = pd.to_datetime(data["game_date"], errors="coerce")
    if parsed_dates.isna().any():
        raise LoaderError(f"game_date has {int(parsed_dates.isna().sum())} invalid value(s).")
    data["game_date"] = parsed_dates.dt.date

    return data


def prepare_players(data: pd.DataFrame) -> list[dict[str, Any]]:
    """Prepare distinct MLB players before resolving internal player_id values."""
    players: dict[int, dict[str, Any]] = {}

    for row in data.itertuples(index=False):
        pitcher_mlb_id = int(row.pitcher)
        pitcher_record = players.setdefault(
            pitcher_mlb_id,
            {
                "mlb_id": pitcher_mlb_id,
                "player_name": None,
                "throws": None,
                "bats": None,
            },
        )
        pitcher_record["player_name"] = (
            optional_text(row.player_name) or pitcher_record["player_name"]
        )
        pitcher_record["throws"] = optional_text(row.p_throws) or pitcher_record["throws"]

        batter_mlb_id = int(row.batter)
        players.setdefault(
            batter_mlb_id,
            {
                "mlb_id": batter_mlb_id,
                # Savant's pitcher search does not provide batter names or
                # true switch-hitter status. These can be enriched later.
                "player_name": None,
                "throws": None,
                "bats": None,
            },
        )

    return list(players.values())


def prepare_games(data: pd.DataFrame) -> list[dict[str, Any]]:
    """Prepare one consistent record per game_pk."""
    columns = ["game_pk", "game_date", "game_type", "home_team", "away_team"]
    distinct = data[columns].drop_duplicates()
    conflict_mask = distinct["game_pk"].duplicated(keep=False)
    if conflict_mask.any():
        conflicts = distinct.loc[conflict_mask, "game_pk"].drop_duplicates().head(10)
        raise LoaderError(
            "The CSV has conflicting game information for game_pk value(s): "
            + ", ".join(conflicts.astype(str))
        )

    records: list[dict[str, Any]] = []
    for row in distinct.itertuples(index=False):
        records.append(
            {
                "game_pk": int(row.game_pk),
                "game_date": row.game_date,
                "game_type": optional_text(row.game_type),
                "home_team": str(row.home_team).strip().upper(),
                "away_team": str(row.away_team).strip().upper(),
            }
        )
    return records


def prepare_pitches(
    data: pd.DataFrame, player_id_by_mlb_id: dict[int, int]
) -> list[dict[str, Any]]:
    """Map the complete cleaned Savant contract to the pitches table."""
    records: list[dict[str, Any]] = []

    for row in data.itertuples(index=False):
        pitcher_mlb_id = int(row.pitcher)
        batter_mlb_id = int(row.batter)
        try:
            pitcher_id = player_id_by_mlb_id[pitcher_mlb_id]
            batter_id = player_id_by_mlb_id[batter_mlb_id]
        except KeyError as exc:
            raise LoaderError(f"Player ID mapping is missing MLB ID {exc.args[0]}.") from exc

        records.append(
            {
                "pitch_id": str(row.pitch_id),
                "game_pk": int(row.game_pk),
                "pitcher_id": pitcher_id,
                "batter_id": batter_id,
                "at_bat_number": int(row.at_bat_number),
                "pitch_number": int(row.pitch_number),
                "inning": optional_integer(row.inning),
                "inning_half": optional_text(row.inning_topbot),
                "outs_when_up": optional_integer(row.outs_when_up),
                "batter_side": optional_text(row.stand),
                "pitch_type": optional_text(row.pitch_type),
                "pitch_name": optional_text(row.pitch_name),
                "velocity": optional_float(row.release_speed),
                "effective_velocity": optional_float(row.effective_speed),
                "spin_rate": optional_float(row.release_spin_rate),
                "horizontal_break": optional_float(row.pfx_x),
                "vertical_break": optional_float(row.pfx_z),
                "release_extension": optional_float(row.release_extension),
                "release_pos_x": optional_float(row.release_pos_x),
                "release_pos_y": optional_float(row.release_pos_y),
                "release_pos_z": optional_float(row.release_pos_z),
                "plate_x": optional_float(row.plate_x),
                "plate_z": optional_float(row.plate_z),
                "strike_zone_top": optional_float(row.sz_top),
                "strike_zone_bottom": optional_float(row.sz_bot),
                "arm_angle": optional_float(row.arm_angle),
                "zone": optional_integer(row.zone),
                "balls": int(row.balls),
                "strikes": int(row.strikes),
                "description": optional_text(row.description),
                "events": optional_text(row.events, none_placeholder=True),
                "batted_ball_type": optional_text(row.bb_type, none_placeholder=True),
                "is_strike": parse_boolean(row.is_strike),
                "is_swing": parse_boolean(row.is_swing),
                "is_contact": parse_boolean(row.is_contact),
                "is_whiff": parse_boolean(row.is_whiff),
                "is_csw": parse_boolean(row.is_csw),
                "is_in_zone": parse_boolean(row.is_in_zone),
                "is_chase": parse_boolean(row.is_chase),
                "times_through_order": optional_integer(row.times_through_order),
                "exit_velocity": optional_float(row.launch_speed),
                "launch_angle": optional_float(row.launch_angle),
                "hit_distance": optional_float(row.hit_distance_sc),
                "estimated_ba": optional_float(row.estimated_ba_using_speedangle),
                "estimated_woba": optional_float(row.estimated_woba_using_speedangle),
                "woba_value": optional_float(row.woba_value),
                "delta_run_expectancy": optional_float(row.delta_run_exp),
                "bat_speed": optional_float(row.bat_speed),
                "swing_length": optional_float(row.swing_length),
                "is_hard_hit": parse_boolean(row.is_hard_hit),
                "home_score": optional_integer(row.home_score),
                "away_score": optional_integer(row.away_score),
                "batter_score": optional_integer(row.bat_score),
                "fielding_score": optional_integer(row.fld_score),
            }
        )

    return records


def prepare_videos(data: pd.DataFrame) -> list[dict[str, Any]]:
    """Prepare videos only when the pitch has a populated URL."""
    records: list[dict[str, Any]] = []

    for row in data.itertuples(index=False):
        video_url = optional_text(row.video_url)
        available = parse_boolean(row.has_video) and video_url is not None
        if not available:
            continue

        records.append(
            {
                "pitch_id": str(row.pitch_id),
                "video_url": video_url,
                "video_type": optional_text(row.video_level) or "Pitch",
                "video_available": True,
                "notes": optional_text(row.video_notes),
            }
        )

    return records


def verify_schema(cursor: psycopg.Cursor[Any]) -> None:
    """Stop early when schema.sql has not been run in the selected database."""
    cursor.execute(
        """
        SELECT table_name
        FROM information_schema.tables
        WHERE table_schema = 'public'
        """
    )
    existing_tables = {row[0] for row in cursor.fetchall()}
    missing_tables = sorted(EXPECTED_TABLES - existing_tables)
    if missing_tables:
        raise LoaderError(
            "The database is missing tables from schema.sql: " + ", ".join(missing_tables)
        )


def count_existing(cursor: psycopg.Cursor[Any], query: str, ids: list[Any]) -> int:
    """Count source records that already exist before an idempotent upsert."""
    if not ids:
        return 0
    cursor.execute(query, (ids,))
    return int(cursor.fetchone()[0])


def load_database(
    data: pd.DataFrame,
    *,
    host: str | None = None,
    port: int = 5432,
    database: str | None = None,
    user: str | None = None,
    password: str | None = None,
    connection_string: str | None = None,
) -> dict[str, Any]:
    """Load every entity inside one atomic PostgreSQL transaction."""
    players = prepare_players(data)
    games = prepare_games(data)
    source_pitch_ids = data["pitch_id"].astype(str).tolist()

    if connection_string:
        connection_args = (connection_string,)
        connection_kwargs: dict[str, Any] = {"connect_timeout": 10}
        expected_database = None
    else:
        missing = [
            name
            for name, value in (
                ("host", host),
                ("database", database),
                ("user", user),
                ("password", password),
            )
            if not value
        ]
        if missing:
            raise LoaderError(
                "Database connection is missing: " + ", ".join(missing)
            )
        connection_args = ()
        connection_kwargs = {
            "host": host,
            "port": port,
            "dbname": database,
            "user": user,
            "password": password,
            "connect_timeout": 10,
        }
        expected_database = database

    # autocommit=True plus transaction() gives us one explicit atomic load:
    # any failure rolls back all inserted or updated records.
    with psycopg.connect(
        *connection_args, **connection_kwargs, autocommit=True
    ) as connection:
        with connection.transaction():
            with connection.cursor() as cursor:
                cursor.execute("SELECT current_database(), current_user")
                connected_database, connected_user = cursor.fetchone()
                if expected_database and connected_database != expected_database:
                    raise LoaderError(
                        f"Connected to {connected_database!r}, expected "
                        f"{expected_database!r}."
                    )

                verify_schema(cursor)

                player_mlb_ids = [row["mlb_id"] for row in players]
                game_ids = [row["game_pk"] for row in games]

                existing_players = count_existing(
                    cursor,
                    "SELECT COUNT(*) FROM players WHERE mlb_id = ANY(%s)",
                    player_mlb_ids,
                )
                existing_games = count_existing(
                    cursor,
                    "SELECT COUNT(*) FROM games WHERE game_pk = ANY(%s)",
                    game_ids,
                )
                existing_pitches = count_existing(
                    cursor,
                    "SELECT COUNT(*) FROM pitches WHERE pitch_id = ANY(%s)",
                    source_pitch_ids,
                )
                existing_videos = count_existing(
                    cursor,
                    "SELECT COUNT(*) FROM videos WHERE pitch_id = ANY(%s)",
                    source_pitch_ids,
                )

                # The foreign-key parent tables must be loaded first.
                cursor.executemany(PLAYER_UPSERT_SQL, players)
                cursor.executemany(GAME_UPSERT_SQL, games)

                cursor.execute(
                    """
                    SELECT player_id, mlb_id
                    FROM players
                    WHERE mlb_id = ANY(%s)
                    """,
                    (player_mlb_ids,),
                )
                player_id_by_mlb_id = {
                    int(mlb_id): int(player_id) for player_id, mlb_id in cursor.fetchall()
                }
                if len(player_id_by_mlb_id) != len(player_mlb_ids):
                    raise LoaderError("Not every MLB player ID resolved to players.player_id.")

                pitches = prepare_pitches(data, player_id_by_mlb_id)
                videos = prepare_videos(data)

                cursor.executemany(PITCH_UPSERT_SQL, pitches)
                cursor.executemany(VIDEO_UPSERT_SQL, videos)

                # SQL duplicate check. The primary key should make this impossible,
                # but the explicit query documents and verifies the guarantee.
                cursor.execute(
                    """
                    SELECT pitch_id, COUNT(*) AS duplicate_count
                    FROM pitches
                    GROUP BY pitch_id
                    HAVING COUNT(*) > 1
                    """
                )
                duplicate_rows = cursor.fetchall()
                if duplicate_rows:
                    raise LoaderError(f"Duplicate pitch IDs found in PostgreSQL: {duplicate_rows}")

                # Verify every source pitch can join to both player roles and its game.
                cursor.execute(
                    """
                    SELECT COUNT(*)
                    FROM pitches AS p
                    INNER JOIN games AS g
                        ON g.game_pk = p.game_pk
                    INNER JOIN players AS pitcher
                        ON pitcher.player_id = p.pitcher_id
                    INNER JOIN players AS batter
                        ON batter.player_id = p.batter_id
                    WHERE p.pitch_id = ANY(%s)
                    """,
                    (source_pitch_ids,),
                )
                joined_pitch_count = int(cursor.fetchone()[0])
                if joined_pitch_count != len(source_pitch_ids):
                    raise LoaderError(
                        "Foreign-key join verification failed: "
                        f"expected {len(source_pitch_ids)}, found {joined_pitch_count}."
                    )

                cursor.execute(
                    """
                    SELECT
                        COALESCE(pitcher.player_name, pitcher.mlb_id::text) AS pitcher,
                        p.pitch_type,
                        COUNT(*) AS pitch_count,
                        ROUND(AVG(p.velocity)::numeric, 1) AS average_velocity
                    FROM pitches AS p
                    INNER JOIN players AS pitcher
                        ON pitcher.player_id = p.pitcher_id
                    WHERE p.pitch_id = ANY(%s)
                    GROUP BY
                        pitcher.player_name,
                        pitcher.mlb_id,
                        p.pitch_type
                    ORDER BY pitch_count DESC
                    """,
                    (source_pitch_ids,),
                )
                pitch_summary = cursor.fetchall()

                cursor.execute(
                    """
                    SELECT
                        (SELECT COUNT(*) FROM players),
                        (SELECT COUNT(*) FROM games),
                        (SELECT COUNT(*) FROM pitches),
                        (SELECT COUNT(*) FROM videos)
                    """
                )
                total_players, total_games, total_pitches, total_videos = map(
                    int, cursor.fetchone()
                )

    return {
        "database": connected_database,
        "user": connected_user,
        "source": {
            "players": len(players),
            "games": len(games),
            "pitches": len(source_pitch_ids),
            "videos": len(videos),
        },
        "new": {
            "players": len(players) - existing_players,
            "games": len(games) - existing_games,
            "pitches": len(source_pitch_ids) - existing_pitches,
            "videos": len(videos) - existing_videos,
        },
        "existing": {
            "players": existing_players,
            "games": existing_games,
            "pitches": existing_pitches,
            "videos": existing_videos,
        },
        "totals": {
            "players": total_players,
            "games": total_games,
            "pitches": total_pitches,
            "videos": total_videos,
        },
        "pitch_summary": pitch_summary,
    }


def print_report(report: dict[str, Any]) -> None:
    """Print an interview-friendly record and aggregate summary."""
    print("\nDatabase load completed successfully")
    print(f"Database: {report['database']}")
    print(f"Connected user: {report['user']}")

    print("\nRecords prepared from the CSV")
    for table, count in report["source"].items():
        print(f"  {table:<8} {count:>6,}")

    print("\nLoad result")
    for table in ["players", "games", "pitches", "videos"]:
        print(
            f"  {table:<8} "
            f"new={report['new'][table]:>6,}  "
            f"updated/existing={report['existing'][table]:>6,}"
        )

    print("\nCurrent database totals")
    for table, count in report["totals"].items():
        print(f"  {table:<8} {count:>6,}")

    print("\nPitch-type aggregate query")
    print("  Pitcher | Type | Pitches | Avg. velocity")
    for pitcher, pitch_type, pitch_count, average_velocity in report["pitch_summary"]:
        velocity_text = "NULL" if average_velocity is None else str(average_velocity)
        print(f"  {pitcher} | {pitch_type} | {pitch_count} | {velocity_text}")

    print("\nDuplicate pitch IDs in PostgreSQL: 0")
    print("Foreign-key join verification: passed")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Load a cleaned Savant CSV into baseball_video_scouting."
    )
    parser.add_argument(
        "--csv",
        type=Path,
        default=Path("data/processed/Messick_cleaned.csv"),
        help="Path to the cleaned CSV (default: data/processed/Messick_cleaned.csv).",
    )
    parser.add_argument("--host", default="localhost")
    parser.add_argument("--port", type=int, default=5432)
    parser.add_argument("--database", default="baseball_video_scouting")
    parser.add_argument("--user", default="postgres")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    password = os.getenv("PGPASSWORD")
    if not password:
        password = getpass.getpass(f"PostgreSQL password for {args.user}: ")

    try:
        data = load_cleaned_csv(args.csv)
        report = load_database(
            data,
            host=args.host,
            port=args.port,
            database=args.database,
            user=args.user,
            password=password,
        )
        print_report(report)
    except LoaderError as exc:
        print(f"Load stopped: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
    except psycopg.OperationalError as exc:
        print(
            "Could not connect to PostgreSQL. Confirm the server is running and "
            "the host, port, database, username, and password are correct.\n"
            f"PostgreSQL message: {exc}",
            file=sys.stderr,
        )
        raise SystemExit(1) from exc
    except psycopg.Error as exc:
        print(
            "PostgreSQL rejected the load. The transaction was rolled back, so a "
            "partial dataset was not saved.\n"
            f"PostgreSQL message: {exc}",
            file=sys.stderr,
        )
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
