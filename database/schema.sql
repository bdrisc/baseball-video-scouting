-- Baseball Video Scouting relational schema
-- Safe to run repeatedly for new installations. Apply files in database/migrations
-- to upgrade an existing database.

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
    season SMALLINT GENERATED ALWAYS AS (
        EXTRACT(YEAR FROM game_date)::SMALLINT
    ) STORED,
    game_type VARCHAR(2),
    home_team VARCHAR(5) NOT NULL,
    away_team VARCHAR(5) NOT NULL,
    CONSTRAINT games_season_check CHECK (season BETWEEN 1876 AND 2200)
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
    outs_when_up SMALLINT CHECK (outs_when_up BETWEEN 0 AND 2),
    batter_side VARCHAR(1),
    pitch_type VARCHAR(10),
    pitch_name VARCHAR(50),
    velocity DOUBLE PRECISION,
    effective_velocity DOUBLE PRECISION,
    spin_rate DOUBLE PRECISION,
    horizontal_break DOUBLE PRECISION,
    vertical_break DOUBLE PRECISION,
    release_extension DOUBLE PRECISION,
    release_pos_x DOUBLE PRECISION,
    release_pos_y DOUBLE PRECISION,
    release_pos_z DOUBLE PRECISION,
    plate_x DOUBLE PRECISION,
    plate_z DOUBLE PRECISION,
    strike_zone_top DOUBLE PRECISION,
    strike_zone_bottom DOUBLE PRECISION,
    arm_angle DOUBLE PRECISION,
    zone SMALLINT CHECK (zone BETWEEN 1 AND 14),
    balls SMALLINT NOT NULL CHECK (balls BETWEEN 0 AND 3),
    strikes SMALLINT NOT NULL CHECK (strikes BETWEEN 0 AND 2),
    description TEXT,
    events TEXT,
    batted_ball_type VARCHAR(30),
    is_strike BOOLEAN NOT NULL DEFAULT FALSE,
    is_swing BOOLEAN NOT NULL DEFAULT FALSE,
    is_contact BOOLEAN NOT NULL DEFAULT FALSE,
    is_whiff BOOLEAN NOT NULL DEFAULT FALSE,
    is_csw BOOLEAN NOT NULL DEFAULT FALSE,
    is_in_zone BOOLEAN NOT NULL DEFAULT FALSE,
    is_chase BOOLEAN NOT NULL DEFAULT FALSE,
    times_through_order SMALLINT CHECK (times_through_order > 0),
    exit_velocity DOUBLE PRECISION,
    launch_angle DOUBLE PRECISION,
    hit_distance DOUBLE PRECISION,
    estimated_ba DOUBLE PRECISION,
    estimated_woba DOUBLE PRECISION,
    woba_value DOUBLE PRECISION,
    delta_run_expectancy DOUBLE PRECISION,
    bat_speed DOUBLE PRECISION,
    swing_length DOUBLE PRECISION,
    is_hard_hit BOOLEAN NOT NULL DEFAULT FALSE,
    home_score SMALLINT CHECK (home_score >= 0),
    away_score SMALLINT CHECK (away_score >= 0),
    batter_score SMALLINT CHECK (batter_score >= 0),
    fielding_score SMALLINT CHECK (fielding_score >= 0),
    CONSTRAINT pitches_batter_side_check
        CHECK (batter_side IS NULL OR batter_side IN ('L', 'R')),
    CONSTRAINT pitches_inning_half_check
        CHECK (inning_half IS NULL OR LOWER(inning_half) IN ('top', 'bot', 'bottom')),
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

CREATE INDEX IF NOT EXISTS players_name_lower_idx
    ON players (LOWER(player_name));

CREATE INDEX IF NOT EXISTS games_season_date_idx
    ON games (season, game_date, game_pk);

CREATE INDEX IF NOT EXISTS games_team_date_idx
    ON games (home_team, away_team, game_date);

CREATE INDEX IF NOT EXISTS pitches_pitcher_id_idx
    ON pitches (pitcher_id);

CREATE INDEX IF NOT EXISTS pitches_batter_id_idx
    ON pitches (batter_id);

CREATE INDEX IF NOT EXISTS pitches_game_pk_idx
    ON pitches (game_pk);

CREATE INDEX IF NOT EXISTS pitches_pitcher_game_order_idx
    ON pitches (pitcher_id, game_pk, at_bat_number, pitch_number);

CREATE INDEX IF NOT EXISTS pitches_pitcher_type_count_side_idx
    ON pitches (pitcher_id, pitch_type, balls, strikes, batter_side);

CREATE INDEX IF NOT EXISTS pitches_pitcher_velocity_idx
    ON pitches (pitcher_id, velocity);

CREATE INDEX IF NOT EXISTS pitches_pitcher_location_idx
    ON pitches (pitcher_id, plate_x, plate_z);

CREATE INDEX IF NOT EXISTS pitches_pitcher_outcome_idx
    ON pitches (pitcher_id, description, events);

CREATE INDEX IF NOT EXISTS pitches_pitcher_flags_idx
    ON pitches (
        pitcher_id,
        is_swing,
        is_whiff,
        is_in_zone,
        is_chase,
        is_hard_hit
    );

CREATE INDEX IF NOT EXISTS videos_pitch_available_idx
    ON videos (pitch_id)
    WHERE video_available IS TRUE;

CREATE INDEX IF NOT EXISTS playlist_items_order_idx
    ON playlist_items (playlist_id, display_order);
