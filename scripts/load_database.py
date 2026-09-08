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
    INSERT INTO games (game_pk, game_date, home_team, away_team)
    VALUES (%(game_pk)s, %(game_date)s, %(home_team)s, %(away_team)s)
    ON CONFLICT (game_pk) DO UPDATE
    SET
        game_date = EXCLUDED.game_date,
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
        batter_side,
        pitch_type,
        velocity,
        spin_rate,
        horizontal_break,
        vertical_break,
        release_extension,
        plate_x,
        plate_z,
        balls,
        strikes,
        description,
        events,
        exit_velocity,
        launch_angle
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
        %(batter_side)s,
        %(pitch_type)s,
        %(velocity)s,
        %(spin_rate)s,
        %(horizontal_break)s,
        %(vertical_break)s,
        %(release_extension)s,
        %(plate_x)s,
        %(plate_z)s,
        %(balls)s,
        %(strikes)s,
        %(description)s,
        %(events)s,
        %(exit_velocity)s,
        %(launch_angle)s
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
        batter_side = EXCLUDED.batter_side,
        pitch_type = EXCLUDED.pitch_type,
        velocity = EXCLUDED.velocity,
        spin_rate = EXCLUDED.spin_rate,
        horizontal_break = EXCLUDED.horizontal_break,
        vertical_break = EXCLUDED.vertical_break,
        release_extension = EXCLUDED.release_extension,
        plate_x = EXCLUDED.plate_x,
        plate_z = EXCLUDED.plate_z,
        balls = EXCLUDED.balls,
        strikes = EXCLUDED.strikes,
        description = EXCLUDED.description,
        events = EXCLUDED.events,
        exit_velocity = EXCLUDED.exit_velocity,
        launch_angle = EXCLUDED.launch_angle
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
    columns = ["game_pk", "game_date", "home_team", "away_team"]
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
                "home_team": str(row.home_team).strip().upper(),
                "away_team": str(row.away_team).strip().upper(),
            }
        )
    return records


def prepare_pitches(
    data: pd.DataFrame, player_id_by_mlb_id: dict[int, int]
) -> list[dict[str, Any]]:
    """Map Savant fields to the relational pitches table."""
    records: list[dict[str, Any]] = []

    for row in data.itertuples(index=False):
        pitcher_mlb_id = int(row.pitcher)
        batter_mlb_id = int(row.batter)
        try:
            pitcher_id = player_id_by_mlb_id[pitcher_mlb_id]
            batter_id = player_id_by_mlb_id[batter_mlb_id]
        except KeyError as exc:
            raise LoaderError(f"Player ID mapping is missing MLB ID {exc.args[0]}.") from exc

        inning = optional_float(row.inning)
        records.append(
            {
                "pitch_id": str(row.pitch_id),
                "game_pk": int(row.game_pk),
                "pitcher_id": pitcher_id,
                "batter_id": batter_id,
                "at_bat_number": int(row.at_bat_number),
                "pitch_number": int(row.pitch_number),
                "inning": int(inning) if inning is not None else None,
                "inning_half": optional_text(row.inning_topbot),
                "batter_side": optional_text(row.stand),
                "pitch_type": optional_text(row.pitch_type),
                "velocity": optional_float(row.release_speed),
                "spin_rate": optional_float(row.release_spin_rate),
                "horizontal_break": optional_float(row.pfx_x),
                "vertical_break": optional_float(row.pfx_z),
                "release_extension": optional_float(row.release_extension),
                "plate_x": optional_float(row.plate_x),
                "plate_z": optional_float(row.plate_z),
                "balls": int(row.balls),
                "strikes": int(row.strikes),
                "description": optional_text(row.description),
                "events": optional_text(row.events, none_placeholder=True),
                "exit_velocity": optional_float(row.launch_speed),
                "launch_angle": optional_float(row.launch_angle),
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
    host: str,
    port: int,
    database: str,
    user: str,
    password: str,
) -> dict[str, Any]:
    """Load every entity inside one atomic PostgreSQL transaction."""
    players = prepare_players(data)
    games = prepare_games(data)
    source_pitch_ids = data["pitch_id"].astype(str).tolist()

    connection_kwargs = {
        "host": host,
        "port": port,
        "dbname": database,
        "user": user,
        "password": password,
        "connect_timeout": 10,
    }

    # autocommit=True plus transaction() gives us one explicit atomic load:
    # any failure rolls back all inserted or updated records.
    with psycopg.connect(**connection_kwargs, autocommit=True) as connection:
        with connection.transaction():
            with connection.cursor() as cursor:
                cursor.execute("SELECT current_database(), current_user")
                connected_database, connected_user = cursor.fetchone()
                if connected_database != database:
                    raise LoaderError(
                        f"Connected to {connected_database!r}, expected {database!r}."
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
