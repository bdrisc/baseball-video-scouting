-- Baseball Video Scouting relational schema
-- Safe to run repeatedly: existing tables and indexes are preserved.

CREATE TABLE IF NOT EXISTS players (
    player_id BIGSERIAL PRIMARY KEY,
    mlb_id BIGINT NOT NULL UNIQUE,
    player_name TEXT,
    throws VARCHAR(1),
    bats VARCHAR(1),
    CONSTRAINT players_throws_check
        CHECK (throws IS NULL OR throws IN ('L', 'R')),
    CONSTRAINT players_bats_check
        CHECK (bats IS NULL OR bats IN ('L', 'R', 'S'))
);

CREATE TABLE IF NOT EXISTS games (
    game_pk BIGINT PRIMARY KEY,
    game_date DATE NOT NULL,
    home_team VARCHAR(5) NOT NULL,
    away_team VARCHAR(5) NOT NULL
);

CREATE TABLE IF NOT EXISTS pitches (
    pitch_id VARCHAR(100) PRIMARY KEY,
    game_pk BIGINT NOT NULL REFERENCES games(game_pk),
    pitcher_id BIGINT NOT NULL REFERENCES players(player_id),
    batter_id BIGINT NOT NULL REFERENCES players(player_id),
    at_bat_number INTEGER NOT NULL CHECK (at_bat_number > 0),
    pitch_number INTEGER NOT NULL CHECK (pitch_number > 0),
    inning INTEGER CHECK (inning > 0),
    inning_half VARCHAR(10),
    batter_side VARCHAR(1),
    pitch_type VARCHAR(10),
    velocity DOUBLE PRECISION,
    spin_rate DOUBLE PRECISION,
    horizontal_break DOUBLE PRECISION,
    vertical_break DOUBLE PRECISION,
    release_extension DOUBLE PRECISION,
    plate_x DOUBLE PRECISION,
    plate_z DOUBLE PRECISION,
    balls SMALLINT NOT NULL CHECK (balls BETWEEN 0 AND 3),
    strikes SMALLINT NOT NULL CHECK (strikes BETWEEN 0 AND 2),
    description TEXT,
    events TEXT,
    exit_velocity DOUBLE PRECISION,
    launch_angle DOUBLE PRECISION,
    CONSTRAINT pitches_batter_side_check
        CHECK (batter_side IS NULL OR batter_side IN ('L', 'R')),
    CONSTRAINT pitches_natural_key_unique
        UNIQUE (game_pk, at_bat_number, pitch_number)
);

CREATE TABLE IF NOT EXISTS videos (
    video_id BIGSERIAL PRIMARY KEY,
    pitch_id VARCHAR(100) NOT NULL UNIQUE
        REFERENCES pitches(pitch_id) ON DELETE CASCADE,
    video_url TEXT NOT NULL,
    video_type VARCHAR(50),
    video_available BOOLEAN NOT NULL DEFAULT TRUE,
    notes TEXT
);

CREATE TABLE IF NOT EXISTS playlists (
    playlist_id BIGSERIAL PRIMARY KEY,
    playlist_name VARCHAR(120) NOT NULL,
    description VARCHAR(1000),
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS playlist_items (
    playlist_id BIGINT NOT NULL
        REFERENCES playlists(playlist_id) ON DELETE CASCADE,
    pitch_id VARCHAR(100) NOT NULL
        REFERENCES pitches(pitch_id) ON DELETE CASCADE,
    display_order INTEGER NOT NULL CHECK (display_order > 0),
    scouting_note VARCHAR(2000),
    PRIMARY KEY (playlist_id, pitch_id),
    CONSTRAINT playlist_items_order_unique
        UNIQUE (playlist_id, display_order)
);

CREATE INDEX IF NOT EXISTS pitches_pitcher_id_idx
    ON pitches (pitcher_id);

CREATE INDEX IF NOT EXISTS pitches_game_pk_idx
    ON pitches (game_pk);

CREATE INDEX IF NOT EXISTS pitches_filter_idx
    ON pitches (pitcher_id, pitch_type, balls, strikes, batter_side);

CREATE INDEX IF NOT EXISTS videos_available_idx
    ON videos (video_available);

CREATE INDEX IF NOT EXISTS playlist_items_order_idx
    ON playlist_items (playlist_id, display_order);
