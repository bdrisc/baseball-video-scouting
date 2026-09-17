# PostgreSQL schema

`schema.sql` defines the normalized tables, primary keys, foreign keys,
uniqueness rules, checks, and query indexes required by the loader and API.

## New database

From the repository root:

```powershell
psql -U postgres -d baseball_video_scouting -f database\schema.sql
```

## Existing database

Apply numbered migration files in order. For the season-wide expansion:

```powershell
$env:PGSSLMODE = "require"
psql $env:DATABASE_URL -v ON_ERROR_STOP=1 `
  -f database\migrations\001_season_wide_schema.sql
```

`ON_ERROR_STOP=1` prevents psql from continuing after a failed statement.
The migration is idempotent and preserves the existing Parker Messick sample.
It adds:

- a generated season and game type;
- the broader Statcast pitch, release, location, outcome, score, and
  bat-tracking fields already produced by the cleaning pipeline;
- derived swing, whiff, zone, chase, CSW, and hard-hit flags;
- indexes for pitcher-season retrieval, pitch filtering, plotting, outcomes,
  batter lookups, name search, and available video.

Step 3 adds `import_batches` and `import_errors`. Apply it after migration 001:

```powershell
psql $env:DATABASE_URL -v ON_ERROR_STOP=1 `
  -f database\migrations\002_import_batch_logging.sql
```

It records each file attempt, SHA-256 identity, status, row counts, and durable
failure details. Successful hashes can then be skipped safely on later runs.

Step 6 normalizes teams and adds season-wide pitcher-discovery indexes. Apply
it after migration 002 and before loading additional season-wide files:

```powershell
psql $env:DATABASE_URL -v ON_ERROR_STOP=1 `
  -f database\migrations\003_teams_seasons_pitcher_search.sql
```

The migration preserves the original `home_team` and `away_team` codes for
backward compatibility, backfills foreign keys to the new `teams` table, and
then makes those relationships required. It also enables PostgreSQL trigram
search for indexed contains-style pitcher-name queries and adds season/team
indexes used by the discovery API.

The optional `model_predictions` table should be introduced through a later
migration only if a production model contract is defined.
