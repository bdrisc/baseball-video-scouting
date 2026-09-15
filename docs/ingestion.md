# Statcast download and repeatable ingestion

This workflow is for the private season-wide application. Python downloads
league-wide pitch data as resumable daily files, and the existing ingestion
command cleans and loads reviewed files into PostgreSQL.

Run every command from the repository root with the Python virtual environment
active. Raw and processed CSV files are ignored by Git and must not be
committed.

## 1. Install the project dependencies

```powershell
python -m pip install -r requirements-dev.txt
```

## 2. Download a date range automatically

Use an explicit start and end date. The end date should normally be the last
completed MLB date rather than today while games are still in progress.

```powershell
python -m scripts.fetch_statcast `
  --start-date 2026-03-01 `
  --end-date 2026-09-11
```

The downloader requests league-wide Statcast data one day at a time and writes:

```text
data/raw/statcast/2026/statcast_2026-03-01.csv
data/raw/statcast/2026/statcast_2026-03-02.csv
```

A date with no returned pitches receives a small `.empty` completion marker.
On a rerun, valid CSV files and empty-day markers are skipped, so an interrupted
download can resume without starting over.

Each downloaded response is checked for required columns, the requested game
date, complete pitch keys, and conflicting duplicates. Temporary failures are
retried with exponential backoff. A one-second pause is used between dates.

To redownload every requested date, add `--force`:

```powershell
python -m scripts.fetch_statcast `
  --start-date 2026-09-01 `
  --end-date 2026-09-11 `
  --force
```

Do not commit these files. The downloader collects Statcast pitch data only; it
does not download or store MLB video.

## 3. Validate one downloaded day without changing PostgreSQL

Start with one date before processing a larger range:

```powershell
python -m scripts.ingest_savant `
  --savant-csv data\raw\statcast\2026\statcast_2026-09-11.csv `
  --expected-season 2026 `
  --dry-run
```

The dry run:

- verifies required Savant columns and values;
- generates stable `game_pk_at_bat_number_pitch_number` pitch IDs;
- rejects duplicate or conflicting pitches;
- standardizes pitch names and derived scouting flags;
- rejects dates outside 2026;
- writes a cleaned CSV under `data/processed`;
- makes no database changes.

Video input is optional. Without a video table, pitches are loaded with no new
video rows. The later official-video matching process can add them by
`pitch_id`.

## 4. Add import tracking to Neon PostgreSQL

Apply the Step 3 migration once before using directory ingestion:

```powershell
$env:PGSSLMODE = "require"

psql $env:DATABASE_URL -v ON_ERROR_STOP=1 `
  -f database\migrations\002_import_batch_logging.sql
```

The migration is safe to rerun. It creates `import_batches` and
`import_errors`, plus indexes used to recognize files that already loaded.

## 5. Load all downloaded days with tracking

After validating a representative day, process the directory:

```powershell
python -m scripts.ingest_savant_directory `
  --input-dir data\raw\statcast\2026 `
  --expected-season 2026
```

For each daily CSV, the command:

- computes a SHA-256 fingerprint;
- skips the file if that exact content already succeeded;
- records a running import batch;
- cleans and atomically loads the file;
- marks successful batches with pitch-row counts;
- records a sanitized error if the file fails;
- continues to the next file.

The command exits with code 1 if any files failed, even though other valid files
may have succeeded. Fix the problem and run the same command again. Successful
files are skipped, while failed files are retried as new attempts.

Use `--stop-on-error` when diagnosing the first bad file. Use `--force` only
when you intentionally want to process files whose exact hashes already
succeeded.

Review recent import history without exposing credentials:

```sql
SELECT
    import_batch_id,
    source_file,
    status,
    rows_loaded,
    new_pitches,
    existing_pitches,
    error_count,
    started_at,
    finished_at
FROM import_batches
ORDER BY import_batch_id DESC
LIMIT 25;
```

Review failures:

```sql
SELECT
    b.source_file,
    e.error_type,
    e.error_message,
    e.created_at
FROM import_errors AS e
INNER JOIN import_batches AS b
    ON b.import_batch_id = e.import_batch_id
ORDER BY e.import_error_id DESC;
```

The error table already supports an optional row number, pitch ID, and JSON
context for future row-level recovery. Step 3 currently records file-level
failures because each daily pitch load is deliberately all-or-nothing.

## 6. Load a reviewed day into Neon PostgreSQL

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
  --savant-csv data\raw\statcast\2026\statcast_2026-09-11.csv `
  --expected-season 2026
```

The database operation is atomic: a failure rolls back the entire file. It is
also idempotent: rerunning the same file updates matching players, games, and
pitches instead of creating duplicates.

Clear the credential afterward:

```powershell
Remove-Item Env:DATABASE_URL -ErrorAction SilentlyContinue
```

## Optional existing video table

A previously verified pitch-keyed video table can still be supplied:

```powershell
python -m scripts.ingest_savant `
  --savant-csv data\raw\statcast\2026\statcast_2026-09-11.csv `
  --video-table data\raw\statcast_2026-09-11_videos.csv `
  --expected-season 2026
```

Do not use `--require-all-video` unless a video table is supplied and every
pitch is expected to match.

Directory ingestion and durable file-level error history are implemented in Step 3.
