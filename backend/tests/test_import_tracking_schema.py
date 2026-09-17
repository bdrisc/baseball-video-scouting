"""Contract tests for PostgreSQL import-batch tracking."""

from __future__ import annotations

from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
SCHEMA_PATH = REPOSITORY_ROOT / "database" / "schema.sql"
MIGRATION_PATH = REPOSITORY_ROOT / "database" / "migrations" / "002_import_batch_logging.sql"


def read_sql(path: Path) -> str:
    return " ".join(path.read_text(encoding="utf-8").lower().split())


def test_base_schema_contains_import_tracking_tables() -> None:
    schema = read_sql(SCHEMA_PATH)

    assert "create table if not exists import_batches" in schema
    assert "create table if not exists import_errors" in schema
    assert "references import_batches(import_batch_id) on delete cascade" in schema
    assert "status in ('running', 'succeeded', 'failed')" in schema


def test_import_tracking_migration_is_rerunnable_and_indexed() -> None:
    migration = read_sql(MIGRATION_PATH)

    assert migration.count("create table if not exists") == 2
    assert migration.count("create index if not exists") == 3
    assert "import_batches_hash_status_idx" in migration
    assert "import_errors_batch_idx" in migration
    assert "source_sha256 varchar(64) not null" in migration


def test_errors_support_future_row_level_context() -> None:
    migration = read_sql(MIGRATION_PATH)

    assert "row_number integer" in migration
    assert "pitch_id varchar(100)" in migration
    assert "error_context jsonb" in migration
