# FastAPI backend

This FastAPI backend queries the PostgreSQL tables created and loaded in Steps
9 and 10. It uses direct, parameterized SQL through Psycopg rather than an ORM.

## 1. Open the repository

The backend lives in this repository structure:

```text
baseball-video-scouting/
└── backend/
    ├── app/
    ├── .env.example
    ├── requirements.txt
    └── README.md
```

Open the `baseball-video-scouting` project folder in VS Code. Then open a new
PowerShell terminal in VS Code and run the following commands from the project
folder.

## 2. Create and activate a virtual environment

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
```

If PowerShell blocks activation, run this once in the same terminal and try the
activation command again:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
```

## 3. Install the backend packages

```powershell
python -m pip install --upgrade pip
python -m pip install -r backend\requirements.txt
```

## 4. Create your private environment file

```powershell
Copy-Item backend\.env.example backend\.env
code backend\.env
```

In `backend/.env`, replace only this placeholder with the password you use to
connect to PostgreSQL:

```text
DB_PASSWORD=replace_with_your_postgres_password
```

Do not commit `.env` to GitHub.

## 5. Start the API

```powershell
python -m uvicorn app.main:app --reload --app-dir backend
```

Keep that terminal open. A successful startup includes a line saying Uvicorn is
running at `http://127.0.0.1:8000`.

Open these pages in your browser:

- API documentation: http://127.0.0.1:8000/docs
- Health check: http://127.0.0.1:8000/health
- Pitchers: http://127.0.0.1:8000/pitchers

## 6. First Swagger test

1. Open `http://127.0.0.1:8000/docs`.
2. Expand `GET /pitchers`.
3. Select **Try it out**, then **Execute**.
4. Copy Parker Messick's `player_id` from the response.
5. Expand `GET /pitches` and set `pitcher_id` to that value.
6. Execute it and confirm the response contains pitch records and video URLs.

For the example 1-2 slider filter, fill in:

```text
pitcher_id=<player_id from GET /pitchers>
pitch_type=SL
balls=1
strikes=2
batter_side=R
```

The equivalent browser URL is:

```text
http://127.0.0.1:8000/pitches?pitcher_id=1&pitch_type=SL&balls=1&strikes=2&batter_side=R
```

Replace `1` with the actual internal `player_id` returned by `/pitchers`.

## Endpoints included

- `GET /health`
- `GET /pitchers`
- `GET /pitchers/{pitcher_id}/games`
- `GET /pitchers/{pitcher_id}/summary`
- `GET /pitches`
- `GET /pitches/{pitch_id}`
- `GET /pitches/{pitch_id}/video`
- `POST /playlists`
- `GET /playlists`
- `PUT /playlists/{playlist_id}`
- `POST /playlists/{playlist_id}/pitches`
- `PUT /playlists/{playlist_id}/items`
- `GET /playlists/{playlist_id}`
- `DELETE /playlists/{playlist_id}/pitches/{pitch_id}`

## Step 19 playlist persistence

`GET /playlists` returns every saved playlist with pitch and video counts.
`PUT /playlists/{playlist_id}` updates the name and description.
`PUT /playlists/{playlist_id}/items` accepts the complete ordered pitch list,
validates every pitch ID and note, and replaces the playlist contents in one
database transaction. This bulk-save route avoids temporary display-order
conflicts while supporting reorder and removal operations from React.

The original single-pitch POST and DELETE endpoints remain available for direct
API use and Swagger testing.

## Automated tests

From the repository root with the virtual environment activated:

```powershell
python -m pip install -r backend\requirements-dev.txt
python -m pytest
```

The suite uses controlled database doubles, so unit and API-validation tests do
not require a password or change the local PostgreSQL database. SQL text and
parameters are still inspected to verify filtering, idempotent upserts, and
playlist behavior.

## Step 12 validation included

The API now validates the following before running a pitch query:

- Pitch IDs must follow `gamePk_atBatNumber_pitchNumber`, such as
  `824566_8_1`.
- Pitch types must be recognized Statcast codes. Lowercase codes are converted
  to uppercase automatically.
- Batter side must be `L` or `R`.
- Balls must be 0-3 and strikes must be 0-2.
- Velocity must be between 0 and 110 mph.
- Plate-x filters must be between -5 and 5 feet; plate-z filters must be
  between -2 and 8 feet.
- Dates must be real ISO dates in `YYYY-MM-DD` form. Start dates cannot come
  after end dates.
- Minimum numerical filters cannot exceed their matching maximum filters.
- Database IDs must be positive integers.
- Playlist names cannot be blank or exceed 100 characters.
- Scouting notes cannot exceed 2,000 characters.
- An unknown pitcher or game returns `404 Not Found` instead of an empty result.

Invalid Pydantic inputs return a structured `422` response containing the
field, a readable message, the error type, and the submitted value when safe.

These valid and invalid cases can be exercised through Swagger and will be
covered by automated tests in Step 22.
