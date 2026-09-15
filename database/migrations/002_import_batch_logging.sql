-- Track repeatable Statcast file imports and durable failure details.
-- Apply after 001_season_wide_schema.sql. Safe to run repeatedly.

CREATE TABLE IF NOT EXISTS import_batches (
    import_batch_id BIGSERIAL PRIMARY KEY,
    source_file TEXT NOT NULL,
    source_sha256 VARCHAR(64) NOT NULL,
    source_size_bytes BIGINT NOT NULL CHECK (source_size_bytes >= 0),
    expected_season SMALLINT,
    status VARCHAR(20) NOT NULL,
    rows_loaded INTEGER CHECK (rows_loaded IS NULL OR rows_loaded >= 0),
    new_pitches INTEGER CHECK (new_pitches IS NULL OR new_pitches >= 0),
    existing_pitches INTEGER CHECK (existing_pitches IS NULL OR existing_pitches >= 0),
    error_count INTEGER NOT NULL DEFAULT 0 CHECK (error_count >= 0),
    started_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    finished_at TIMESTAMPTZ,
    CONSTRAINT import_batches_status_check
        CHECK (status IN ('running', 'succeeded', 'failed')),
    CONSTRAINT import_batches_season_check
        CHECK (expected_season IS NULL OR expected_season BETWEEN 1876 AND 2200),
    CONSTRAINT import_batches_finished_check
        CHECK (
            (status = 'running' AND finished_at IS NULL)
            OR (status IN ('succeeded', 'failed') AND finished_at IS NOT NULL)
        )
);

CREATE TABLE IF NOT EXISTS import_errors (
    import_error_id BIGSERIAL PRIMARY KEY,
    import_batch_id BIGINT NOT NULL
        REFERENCES import_batches(import_batch_id) ON DELETE CASCADE,
    row_number INTEGER CHECK (row_number IS NULL OR row_number > 0),
    pitch_id VARCHAR(100),
    error_type VARCHAR(100) NOT NULL,
    error_message TEXT NOT NULL,
    error_context JSONB NOT NULL DEFAULT '{}'::JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS import_batches_hash_status_idx
    ON import_batches (source_sha256, status, finished_at DESC);

CREATE INDEX IF NOT EXISTS import_batches_status_started_idx
    ON import_batches (status, started_at DESC);

CREATE INDEX IF NOT EXISTS import_errors_batch_idx
    ON import_errors (import_batch_id, import_error_id);
