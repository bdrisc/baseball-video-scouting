# Step 10: private season query and video audit

Run from the repository root with the Python virtual environment active. This
command is **read-only** and requires the private Neon pooled `DATABASE_URL` in
your current shell. Never paste that URL, access tokens, or database passwords
into chat or commit them to Git. The public portfolio database is not used.

## 1. Run the local audit

```powershell
$privateHost = ([Uri]$env:DATABASE_URL).Host
# Compare this hostname against the private-season-wide branch in the Neon
# console before running. Do not use the public portfolio branch.
$privateHost

python -m scripts.audit_private_season --expected-host $privateHost
```

The audit requires all seven date-specific `video_match_report.csv` files from
March 25–31 through September 1–25 in `data/processed/video_matches`.
It checks each report's pitch count against the actual database count for
that date range, lists all review reasons, confirms a fixed five-link random
sample **per month** against stored game, date, pitcher, batter, and available
video link, and prints the URLs for manual checks. Existing curated URLs may
differ from the automatic match; these are listed separately for review.
If it reports a discrepancy, investigate that month before trusting its
coverage figure. The command never rewrites pitches or links.

The benchmark calls the actual Python route handlers with live SQL for
season and team discovery, pitcher search, pitcher games, paginated pitches,
velocity sorting, and aggregate charts. It warms each handler once, then
reports median and worst timing over three runs. The chosen pitcher is the
one with the most pitches in that season; reruns can compare the same
workload. These are **local-to-database** times, not complete authenticated
browser times: AWS API Gateway, Lambda cold start, Cognito, and frontend
rendering are excluded. For an end-to-end check, also time a handful of
page loads in your signed-in private workspace and note whether the first
load is slower than subsequent ones.

## 2. Review video accuracy manually

For each URL printed, open the official Baseball Savant page and confirm:

1. The game date, pitcher, batter, and pitch event are the ones listed.
2. A video actually plays, if you intend to describe it as playable video.
3. Note any wrong pitch, wrong player, broken page, or unplayable video.

Matching a `playId` and importing its official page URL is **not** proof
that every pitch has playable media. The five samples per month provide a
reproducible spot check, not a statistically precise error-rate estimate.
Inspect the unmatched `player_id_mismatch` rows in each month's
`video_match_report.csv` separately; they intentionally have no automatic
video link. If a link is wrong, record its pitch ID and review the cached MLB
game feed before changing any video row.

## 3. Record results

Save the month-by-month pitch/linked counts, review reasons, sampled pitch
IDs, manual outcomes, median/worst handler times, and date of test in your
private notes. Re-run after adding the rest of September or changing indexes.
If a workload times out at 30 seconds or feels slow in the live app, inspect
that query with `EXPLAIN (ANALYZE, BUFFERS)` and tune its SQL/indexes before
making broad index changes.
