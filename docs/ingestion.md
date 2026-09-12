# Repeatable Savant CSV ingestion

This workflow is for the private season-wide application. It starts after a
manual Baseball Savant CSV export and intentionally does not automate scraping
or downloading MLB data.

Run every command from the repository root with the Python virtual environment
active.

## 1. Name and place the export

Use a descriptive month or date range so processed files remain traceable:

```text
data/raw/statcast_2026_april.csv
data/raw/statcast_2026_may.csv
```

Raw and processed CSV files are ignored by Git and must not be committed.

## 2. Validate without changing PostgreSQL

```powershell
python -m scripts.ingest_savant `
  --savant-csv data\raw\statcast_2026_april.csv `
  --expected-season 2026 `
  --dry-run
```

The dry run:

- verifies required Savant columns and values;
- generates stable `game_pk_at_bat_number_pitch_number` pitch IDs;
- rejects duplicate or conflicting pitches;
- standardizes pitch names and derived scouting flags;
- rejects dates outside 2026;
- writes `data/processed/statcast_2026_april_cleaned.csv`;
- makes no database changes.

Video input is optional. Without a video table, pitches are loaded with no new
video rows. The later official-video matching process can add them by
`pitch_id`.

## 3. Load Neon PostgreSQL

Copy the Neon pooled connection string, then keep it only in the current
PowerShell process:

```powershell
$env:DATABASE_URL = [string](Get-Clipboard -Raw)
Set-Clipboard -Value "cleared"
```

Confirm its shape without printing the credential:

```powershell
[PSCustomObject]@{
    CorrectScheme = $env:DATABASE_URL.Trim().StartsWith("postgresql://")
    CorrectDatabase = $env:DATABASE_URL.Contains("/baseball_video_scouting")
    PooledHost = $env:DATABASE_URL.Contains("-pooler")
}
```

All three values should be `True`. Then run:

```powershell
python -m scripts.ingest_savant `
  --savant-csv data\raw\statcast_2026_april.csv `
  --expected-season 2026
```

The database operation is atomic: a failure rolls back the entire file. It is
also idempotent: rerunning the same export updates matching players, games, and
pitches instead of creating duplicates.

Clear the credential afterward:

```powershell
Remove-Item Env:DATABASE_URL -ErrorAction SilentlyContinue
```

## Optional existing video table

A previously verified pitch-keyed video table can still be supplied:

```powershell
python -m scripts.ingest_savant `
  --savant-csv data\raw\statcast_2026_april.csv `
  --video-table data\raw\statcast_2026_april_videos.csv `
  --expected-season 2026
```

Do not use `--require-all-video` unless a video table is supplied and every
pitch is expected to match.

Import-batch history and row-level error storage are deliberately deferred to
Step 3.
