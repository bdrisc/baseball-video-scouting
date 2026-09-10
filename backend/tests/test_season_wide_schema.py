"""Contract tests for the season-wide PostgreSQL schema and migration."""

from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
SCHEMA_PATH = REPOSITORY_ROOT / "database" / "schema.sql"
MIGRATION_PATH = REPOSITORY_ROOT / "database" / "migrations" / "001_season_wide_schema.sql"


def read_sql(path: Path) -> str:
    return " ".join(path.read_text(encoding="utf-8").lower().split())


def test_base_schema_preserves_season_wide_statcast_fields() -> None:
    schema = read_sql(SCHEMA_PATH)

    expected_fragments = (
        "season smallint generated always as",
        "game_type varchar(2)",
        "outs_when_up smallint",
        "pitch_name varchar(50)",
        "effective_velocity double precision",
        "release_pos_x double precision",
        "strike_zone_top double precision",
        "arm_angle double precision",
        "is_whiff boolean not null default false",
        "is_chase boolean not null default false",
        "estimated_woba double precision",
        "delta_run_expectancy double precision",
        "bat_speed double precision",
        "swing_length double precision",
    )

    for fragment in expected_fragments:
        assert fragment in schema


def test_schema_has_indexes_for_season_scale_access_patterns() -> None:
    schema = read_sql(SCHEMA_PATH)

    expected_indexes = (
        "games_season_date_idx",
        "pitches_pitcher_game_order_idx",
        "pitches_pitcher_type_count_side_idx",
        "pitches_pitcher_velocity_idx",
        "pitches_pitcher_location_idx",
        "pitches_pitcher_outcome_idx",
        "pitches_pitcher_flags_idx",
        "videos_pitch_available_idx",
    )

    for index_name in expected_indexes:
        assert f"create index if not exists {index_name}" in schema

    assert "where video_available is true" in schema


def test_existing_database_migration_is_rerunnable_and_backfills_flags() -> None:
    migration = read_sql(MIGRATION_PATH)

    assert migration.count("add column if not exists") >= 25
    assert migration.count("create index if not exists") >= 8
    assert "update pitches set" in migration
    assert "is_whiff =" in migration
    assert "is_in_zone =" in migration
    assert "is_hard_hit =" in migration
    assert "analyze pitches" in migration
