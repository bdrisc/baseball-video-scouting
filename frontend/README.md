# React pitch scouting interface

This folder contains the Vite-powered React interface for the baseball video
scouting project. The Step 14 foundation includes typed API access, responsive
styling, working pitcher and game selectors, and separate component files for
every planned part of the application.

## Automated tests

Install the updated development dependencies and run the frontend suite:

```powershell
cd frontend
npm install
npm run test:run
```

Use `npm run test:coverage` for a coverage report. The tests exercise API
serialization and errors, pitch-table interaction, video navigation, playlist
requests, and advance-report calculations.

## 1. Confirm Node.js is installed

Open a new PowerShell terminal in VS Code and run:

```powershell
node --version
npm --version
```

Use Node.js 24 LTS. Vite 8 requires Node.js 20.19+ or 22.12+; Node 24 satisfies
that requirement. If `node` is not recognized, install Node.js 24 LTS from the
official Node.js download page, close VS Code, reopen it, and run the two
version commands again.

## 2. Confirm the project layout

The local project should now have both applications:

```text
baseball-video-scouting/
├── backend/
└── frontend/
```

The repository keeps the frontend and backend as separate applications.

## 3. Install frontend packages

From the main `baseball-video-scouting` project folder:

```powershell
cd frontend
npm install
```

The first installation creates `node_modules` and `package-lock.json`. Keep
`package-lock.json` when the project is eventually added to Git. Do not commit
`node_modules`.

## 4. Create the frontend environment file

While still in `frontend`:

```powershell
Copy-Item .env.example .env
```

The included value points React to the local FastAPI server:

```text
VITE_API_BASE_URL=http://127.0.0.1:8000
```

## 5. Run both applications

Use two VS Code terminals.

Terminal 1, from the main project folder:

```powershell
.\.venv\Scripts\Activate.ps1
python -m uvicorn app.main:app --reload --app-dir backend
```

Terminal 2:

```powershell
cd frontend
npm run dev
```

Open the address printed by Vite, normally:

```text
http://127.0.0.1:5173
```

## 6. What should work now

- The header says the API is connected to `baseball_video_scouting`.
- The pitcher selector loads data from `GET /pitchers`.
- Parker Messick is selected automatically when he is the only pitcher.
- The game selector loads all five games from
  `GET /pitchers/{pitcher_id}/games`.
- Every planned UI area is its own TypeScript component.
- The layout adjusts for desktop, tablet, and phone widths.

## Step 15 pitch search

After selecting a pitcher, React requests pitches from `GET /pitches`. It sends
a new request whenever the game or a baseball filter changes. Typed number
fields use a 300 millisecond debounce so a user can finish typing before the
request is sent.

Working controls include:

- Game
- Batter side
- Pitch type
- Count
- Pitch result
- Minimum and maximum velocity
- Minimum and maximum horizontal plate location
- Minimum and maximum vertical plate location
- Video availability
- Reset filters

The results area includes the database match count, average velocity, whiffs,
videos available, number of pitch types, a searchable table, video indicators,
row selection, and an Add button. Add stages a pitch in a local queue; database
playlist persistence is intentionally reserved for Step 19.

## Step 16 pitch details

Clicking a pitch-table row now fills the selected-pitch panel with:

- Full pitch name and Statcast code
- Velocity and count
- Spin rate
- Horizontal and vertical movement in inches
- Release extension in feet
- Batter name and side
- Pitch and plate-appearance result
- Horizontal and vertical plate location in feet
- Exit velocity and launch angle when the pitch was put in play
- A working official MLB video button when video is available
- A pitch-specific scouting-notes field with a 2,000-character limit

The source Savant `pfx_x` and `pfx_z` values were loaded into PostgreSQL in
feet, so the interface multiplies them by 12 for the standard baseball movement
display in inches. Plate coordinates and release extension remain in feet.

Notes remain available while the React app is open and are kept separately for
each selected pitch. Step 19 will attach those notes to playlist items and save
them in PostgreSQL.

## Step 17 interactive Plotly charts

Every chart uses the pitches returned by the current API filters, so changing a
game, pitch type, count, batter side, velocity range, location range, result, or
video setting recalculates all six views automatically.

The completed views are:

- Pitch location with a fixed 1.5-3.5 foot strike-zone reference
- Horizontal and induced vertical movement, converted to inches
- Pitch usage as a percentage of the filtered sample
- Average velocity by inning and pitch type
- Pitch-type usage within each count
- Pitch-result distributions against left- and right-handed batters

Clicking a point in the location or movement chart selects the same pitch used
by the table and details panel, highlights its chart marker, and scrolls its
table row into view. Hovering over a point shows the pitch context and values.

## Step 18 official video review

The video panel beside the pitch details now follows the selected table row or
interactive chart point. For the standard `mlb.com/video/...` links in the
database, the panel opens the correct official MLB page in a new tab. This is
more reliable than placing a normal MLB webpage inside an iframe that MLB may
block.

When a link is an official direct `sporty-clips.mlb.com` MP4, the panel first
tries a native HTML5 player. If playback is rejected, the application falls
back to the official external link automatically.

The panel also includes:

- Watch in MLB Film Room
- Previous video
- Next video
- Add to playlist
- Current-video position and linked-video count

Previous and next follow the order of the currently filtered pitch results, so
the video workflow stays aligned with the active game and pitch filters. The
application stores links only; it does not download or host MLB video.

## Step 19 PostgreSQL playlist system

The playlist builder now creates and updates named playlists in PostgreSQL.
Saved playlists can be reopened after a page refresh, edited, and saved again.

The completed workflow supports:

- Playlist name and description
- Suggested example names through the name field
- Adding pitches from the table or video panel
- Moving pitches up and down
- A separate scouting note for every playlist item
- Removing individual pitches or clearing the current queue
- Saving the complete order and notes atomically
- Loading existing playlists from PostgreSQL
- Reviewing linked videos consecutively in playlist order

Select **Review playlist videos** to put the video panel in playlist-review
mode. The previous and next controls then follow the staged playlist instead of
the broader filtered search results. Standard MLB page links continue to open
in MLB's official viewer.

## Step 20 advance report

The report panel now turns the currently filtered pitch sample into an
in-application advance report. It includes:

- Arsenal overview with pitch count, usage, velocity, spin, movement, whiff
  rate per swing, and zone rate
- Primary pitch-usage summary
- First-pitch, pitcher-ahead, hitter-ahead, two-strike, and full-count
  tendencies
- Pitch usage and whiff rate against left- and right-handed hitters
- Zone rate, primary vertical band, primary horizontal lane, and elevated
  fastball rate
- Two-strike pitch usage, whiff rate, best whiff pitch, and recorded strikeouts
- Average and maximum exit velocity, 95+ mph hard-hit rate, home runs, and the
  pitch type with the highest average exit velocity allowed
- A written scouting-observations field saved automatically in the browser
- A reusable link to the active PostgreSQL video playlist

Report calculations use the same pitches loaded by the search page, so every
game or pitch filter updates the report. The heading shows both loaded rows and
total database matches to make the analytical sample transparent.

Saved-playlist links use `?playlist={playlist_id}`. Opening the link reloads the
playlist from PostgreSQL and restores its pitch order and notes. PDF export is
intentionally deferred until the application report is reviewed and stable.

## Component structure

```text
src/
├── components/
│   ├── PitcherSelector.tsx
│   ├── GameSelector.tsx
│   ├── FilterPanel.tsx
│   ├── PitchTable.tsx
│   ├── PitchDetails.tsx
│   ├── StrikeZonePlot.tsx
│   ├── MovementPlot.tsx
│   ├── PitchUsageChart.tsx
│   ├── VelocityByInningChart.tsx
│   ├── UsageByCountChart.tsx
│   ├── ResultsByBatterSideChart.tsx
│   ├── VideoPanel.tsx
│   ├── PlaylistBuilder.tsx
│   ├── ScoutingReport.tsx
│   └── reportMetrics.ts
├── pages/
│   └── ScoutingWorkspace.tsx
├── services/
│   └── api.ts
├── types/
│   └── api.ts
├── App.tsx
├── main.tsx
└── styles.css
```

## Production build check

After confirming the development screen works, run:

```powershell
npm run build
```

A successful build creates `frontend/dist`. That folder is generated output
and should not be committed.
