-- Expand the original portfolio schema for season-wide Statcast ingestion.
-- Apply once to an existing PostgreSQL database. Every DDL statement is
-- idempotent so the migration can be rerun safely.

ALTER TABLE games
    ADD COLUMN IF NOT EXISTS season SMALLINT GENERATED ALWAYS AS (
        EXTRACT(YEAR FROM game_date)::SMALLINT
    ) STORED,
    ADD COLUMN IF NOT EXISTS game_type VARCHAR(2);

ALTER TABLE pitches
    ADD COLUMN IF NOT EXISTS outs_when_up SMALLINT,
    ADD COLUMN IF NOT EXISTS pitch_name VARCHAR(50),
    ADD COLUMN IF NOT EXISTS effective_velocity DOUBLE PRECISION,
    ADD COLUMN IF NOT EXISTS release_pos_x DOUBLE PRECISION,
    ADD COLUMN IF NOT EXISTS release_pos_y DOUBLE PRECISION,
    ADD COLUMN IF NOT EXISTS release_pos_z DOUBLE PRECISION,
    ADD COLUMN IF NOT EXISTS strike_zone_top DOUBLE PRECISION,
    ADD COLUMN IF NOT EXISTS strike_zone_bottom DOUBLE PRECISION,
    ADD COLUMN IF NOT EXISTS arm_angle DOUBLE PRECISION,
    ADD COLUMN IF NOT EXISTS zone SMALLINT,
    ADD COLUMN IF NOT EXISTS batted_ball_type VARCHAR(30),
    ADD COLUMN IF NOT EXISTS is_strike BOOLEAN NOT NULL DEFAULT FALSE,
    ADD COLUMN IF NOT EXISTS is_swing BOOLEAN NOT NULL DEFAULT FALSE,
    ADD COLUMN IF NOT EXISTS is_contact BOOLEAN NOT NULL DEFAULT FALSE,
    ADD COLUMN IF NOT EXISTS is_whiff BOOLEAN NOT NULL DEFAULT FALSE,
    ADD COLUMN IF NOT EXISTS is_csw BOOLEAN NOT NULL DEFAULT FALSE,
    ADD COLUMN IF NOT EXISTS is_in_zone BOOLEAN NOT NULL DEFAULT FALSE,
    ADD COLUMN IF NOT EXISTS is_chase BOOLEAN NOT NULL DEFAULT FALSE,
    ADD COLUMN IF NOT EXISTS times_through_order SMALLINT,
    ADD COLUMN IF NOT EXISTS hit_distance DOUBLE PRECISION,
    ADD COLUMN IF NOT EXISTS estimated_ba DOUBLE PRECISION,
    ADD COLUMN IF NOT EXISTS estimated_woba DOUBLE PRECISION,
    ADD COLUMN IF NOT EXISTS woba_value DOUBLE PRECISION,
    ADD COLUMN IF NOT EXISTS delta_run_expectancy DOUBLE PRECISION,
    ADD COLUMN IF NOT EXISTS bat_speed DOUBLE PRECISION,
    ADD COLUMN IF NOT EXISTS swing_length DOUBLE PRECISION,
    ADD COLUMN IF NOT EXISTS is_hard_hit BOOLEAN NOT NULL DEFAULT FALSE,
    ADD COLUMN IF NOT EXISTS home_score SMALLINT,
    ADD COLUMN IF NOT EXISTS away_score SMALLINT,
    ADD COLUMN IF NOT EXISTS batter_score SMALLINT,
    ADD COLUMN IF NOT EXISTS fielding_score SMALLINT;

-- Populate the new derived flags for pitches already in the database.
UPDATE pitches
SET
    is_strike = COALESCE(
        description IN (
            'called_strike',
            'swinging_strike',
            'swinging_strike_blocked',
            'missed_bunt',
            'foul',
            'foul_tip',
            'foul_bunt'
        ),
        FALSE
    ),
    is_swing = COALESCE(
        description IN (
            'swinging_strike',
            'swinging_strike_blocked',
            'missed_bunt',
            'foul',
            'foul_tip',
            'foul_bunt',
            'hit_into_play'
        ),
        FALSE
    ),
    is_contact = COALESCE(
        description IN ('foul', 'foul_tip', 'foul_bunt', 'hit_into_play'),
        FALSE
    ),
    is_whiff = COALESCE(
        description IN ('swinging_strike', 'swinging_strike_blocked', 'missed_bunt'),
        FALSE
    ),
    is_csw = COALESCE(
        description IN (
            'called_strike',
            'swinging_strike',
            'swinging_strike_blocked',
            'missed_bunt'
        ),
        FALSE
    ),
    is_in_zone = COALESCE(
        zone BETWEEN 1 AND 9,
        plate_x BETWEEN -0.83 AND 0.83
            AND plate_z BETWEEN strike_zone_bottom AND strike_zone_top,
        FALSE
    ),
    is_chase = COALESCE(
        description IN (
            'swinging_strike',
            'swinging_strike_blocked',
            'missed_bunt',
            'foul',
            'foul_tip',
            'foul_bunt',
            'hit_into_play'
        )
        AND NOT COALESCE(
            zone BETWEEN 1 AND 9,
            plate_x BETWEEN -0.83 AND 0.83
                AND plate_z BETWEEN strike_zone_bottom AND strike_zone_top,
            FALSE
        )
        AND (
            zone IS NOT NULL
            OR (
                plate_x IS NOT NULL
                AND plate_z IS NOT NULL
                AND strike_zone_bottom IS NOT NULL
                AND strike_zone_top IS NOT NULL
            )
        ),
        FALSE
    ),
    is_hard_hit = COALESCE(exit_velocity >= 95.0, FALSE);

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'games_season_check'
          AND conrelid = 'games'::regclass
    ) THEN
        ALTER TABLE games
            ADD CONSTRAINT games_season_check
            CHECK (season BETWEEN 1876 AND 2200);
    END IF;

    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'pitches_outs_when_up_check'
          AND conrelid = 'pitches'::regclass
    ) THEN
        ALTER TABLE pitches
            ADD CONSTRAINT pitches_outs_when_up_check
            CHECK (outs_when_up BETWEEN 0 AND 2);
    END IF;

    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'pitches_zone_check'
          AND conrelid = 'pitches'::regclass
    ) THEN
        ALTER TABLE pitches
            ADD CONSTRAINT pitches_zone_check
            CHECK (zone BETWEEN 1 AND 14);
    END IF;

    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'pitches_times_through_order_check'
          AND conrelid = 'pitches'::regclass
    ) THEN
        ALTER TABLE pitches
            ADD CONSTRAINT pitches_times_through_order_check
            CHECK (times_through_order > 0);
    END IF;
END
$$;

DROP INDEX IF EXISTS pitches_filter_idx;
DROP INDEX IF EXISTS videos_available_idx;

CREATE INDEX IF NOT EXISTS players_name_lower_idx
    ON players (LOWER(player_name));

CREATE INDEX IF NOT EXISTS games_season_date_idx
    ON games (season, game_date, game_pk);

CREATE INDEX IF NOT EXISTS games_team_date_idx
    ON games (home_team, away_team, game_date);

CREATE INDEX IF NOT EXISTS pitches_batter_id_idx
    ON pitches (batter_id);

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

ANALYZE players;
ANALYZE games;
ANALYZE pitches;
ANALYZE videos;
