# PostgreSQL schema

`schema.sql` defines the normalized tables, primary keys, foreign keys, uniqueness rules, checks, and query indexes required by the loader and API.

From the repository root:

```powershell
psql -U postgres -d baseball_video_scouting -f database\schema.sql
```

The future `model_predictions` table should be introduced through a migration after the production model contract is defined.
