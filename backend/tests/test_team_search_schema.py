"""Contract tests for normalized teams and scalable name search."""

from __future__ import annotations

from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
SCHEMA_PATH = REPOSITORY_ROOT / "database" / "schema.sql"
MIGRATION_PATH = (
    REPOSITORY_ROOT / "database" / "migrations" / "003_teams_seasons_pitcher_search.sql"
)


def read_sql(path: Path) -> str:
    return " ".join(path.read_text(encoding="utf-8").lower().split())


def test_base_schema_normalizes_game_teams() -> None:
    schema = read_sql(SCHEMA_PATH)

    assert "create table if not exists teams" in schema
    assert "home_team_id bigint not null references teams(team_id)" in schema
    assert "away_team_id bigint not null references teams(team_id)" in schema
    assert "players_name_trgm_idx" in schema
    assert "gin_trgm_ops" in schema


def test_team_migration_backfills_before_enforcing_foreign_keys() -> None:
    migration = read_sql(MIGRATION_PATH)

    assert "insert into teams (team_code)" in migration
    assert "update games as g set home_team_id" in migration
    assert "update games as g set away_team_id" in migration
    assert "alter column home_team_id set not null" in migration
    assert "create extension if not exists pg_trgm" in migration
    assert migration.count("create index if not exists") >= 4
