# Official video matching for the private database

The matcher links raw Statcast pitch rows to official Baseball Savant pitch
pages. It does not download MLB video. Run these commands from the repository
root after activating `.venv` and installing `requirements-dev.txt`.

## 1. Match one completed month

Download that month's daily Statcast CSVs first (see [ingestion](ingestion.md)).
For example, after downloading April:

```powershell
python -m scripts.match_official_videos `
  --input-dir data\raw\statcast\2026 `
  --start-date 2026-04-01 `
  --end-date 2026-04-30
```

The command looks up the MLB game feed once per game, caches JSON under
`data/raw/mlb_game_feeds`, and writes two date-specific CSVs under
`data/processed/video_matches/2026-04-01_2026-04-30`:

- `video_match_report.csv`: every source pitch, with `matched` or `review`
  and a reason such as `missing_play_id`, `player_id_mismatch`, or
  `game_feed_error`.
- `video_links_matched.csv`: only exact pitch-level matches with a valid
  official `playId` and canonical Baseball Savant page URL.

Matches compare the game, at-bat, pitch number, pitcher, batter, inning,
and half-inning when available. Missing or ambiguous information goes to the
review report. A matched **page** does not guarantee playable video exists
for that pitch: check representative links manually and verify playback
availability before claiming complete video coverage. A game feed can change;
use `--refresh` to refetch cached feeds when investigating a discrepancy.

## 2. Import matched links into the private branch

Import pitches into the **private-season-wide** Neon branch before importing
their video links. Migration 003 must also have been applied to that branch.
Copy its *private branch* pooled connection string into the current PowerShell
session; never paste it into chat, a script, or Git:

```powershell
$env:DATABASE_URL = ([string](Get-Clipboard -Raw)).Trim()
Set-Clipboard -Value "cleared"
$privateHost = ([Uri]$env:DATABASE_URL).Host
$links = 'data\processed\video_matches\2026-04-01_2026-04-30\video_links_matched.csv'

python -m scripts.apply_video_links --links $links --expected-host $privateHost
```

Check that `$privateHost` names the **private-season-wide** branch rather than
the public portfolio production endpoint before applying. The command checks
that every pitch exists in this database and that its game, pitcher, and
batter IDs agree. It reports how many links are new and how many pitches
already have a video row. It makes no database changes without `--apply`.

```powershell
python -m scripts.apply_video_links --links $links --expected-host $privateHost --apply
Remove-Item Env:DATABASE_URL
```

The import inserts missing links without replacing curated video links.
Rerunning the same file skips existing video rows. If even one pitch is absent
or mismatched, the command stops before inserting anything. To address review
rows, inspect the official pitch page and resolve them separately; never turn
an uncertain match into an automatic link by guessing its `playId`.

Both the raw MLB feed cache and generated CSVs are ignored by Git. Only
page URLs are stored in PostgreSQL; MLB video media stays on official sites.
