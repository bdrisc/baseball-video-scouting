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

The schema deliberately does not add import-batch tables yet. Batch status and
row-level errors are part of Step 3, after the repeatable ingestion contract is
defined in Step 2.

The optional `model_predictions` table should be introduced through a later
migration only if a production model contract is defined.
