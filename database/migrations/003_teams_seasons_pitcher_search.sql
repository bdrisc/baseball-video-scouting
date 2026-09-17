-- Normalize team identity and add indexes for season-wide pitcher discovery.
-- This migration is idempotent and preserves the existing team-code columns.

CREATE TABLE IF NOT EXISTS teams (
    team_id BIGSERIAL PRIMARY KEY,
    team_code VARCHAR(5) NOT NULL UNIQUE,
    team_name TEXT,
    CONSTRAINT teams_code_check CHECK (team_code = UPPER(team_code))
);

INSERT INTO teams (team_code)
SELECT DISTINCT team_code
FROM (
    SELECT UPPER(home_team) AS team_code FROM games
    UNION
    SELECT UPPER(away_team) AS team_code FROM games
) AS existing_teams
WHERE team_code IS NOT NULL
  AND team_code <> ''
ON CONFLICT (team_code) DO NOTHING;

ALTER TABLE games
    ADD COLUMN IF NOT EXISTS home_team_id BIGINT,
    ADD COLUMN IF NOT EXISTS away_team_id BIGINT;

UPDATE games AS g
SET home_team_id = t.team_id
FROM teams AS t
WHERE g.home_team_id IS NULL
  AND t.team_code = UPPER(g.home_team);

UPDATE games AS g
SET away_team_id = t.team_id
FROM teams AS t
WHERE g.away_team_id IS NULL
  AND t.team_code = UPPER(g.away_team);

DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM games
        WHERE home_team_id IS NULL OR away_team_id IS NULL
    ) THEN
        RAISE EXCEPTION 'Team migration could not resolve every game team code.';
    END IF;

    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'games_home_team_id_fkey'
          AND conrelid = 'games'::regclass
    ) THEN
        ALTER TABLE games
            ADD CONSTRAINT games_home_team_id_fkey
            FOREIGN KEY (home_team_id) REFERENCES teams(team_id);
    END IF;

    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'games_away_team_id_fkey'
          AND conrelid = 'games'::regclass
    ) THEN
        ALTER TABLE games
            ADD CONSTRAINT games_away_team_id_fkey
            FOREIGN KEY (away_team_id) REFERENCES teams(team_id);
    END IF;
END
$$;

ALTER TABLE games
    ALTER COLUMN home_team_id SET NOT NULL,
    ALTER COLUMN away_team_id SET NOT NULL;

CREATE EXTENSION IF NOT EXISTS pg_trgm;

CREATE INDEX IF NOT EXISTS players_name_trgm_idx
    ON players USING GIN (LOWER(player_name) gin_trgm_ops);

CREATE INDEX IF NOT EXISTS teams_code_idx
    ON teams (team_code);

CREATE INDEX IF NOT EXISTS games_season_home_team_idx
    ON games (season, home_team_id, game_date, game_pk);

CREATE INDEX IF NOT EXISTS games_season_away_team_idx
    ON games (season, away_team_id, game_date, game_pk);

ANALYZE teams;
ANALYZE games;
ANALYZE players;
ANALYZE pitches;
