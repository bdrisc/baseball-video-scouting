# Docker setup

Docker Compose runs four cooperating services:

1. `database` starts PostgreSQL 18 and creates the relational schema.
2. `data-loader` waits for PostgreSQL, loads the cleaned CSV when available, and exits successfully.
3. `backend` starts FastAPI only after the loader finishes.
4. `frontend` serves the compiled React application through Nginx and proxies `/api` requests to FastAPI.

The named `postgres_data` volume keeps the container database between normal stops and restarts. The Docker database is separate from the PostgreSQL server already installed on Windows.

## 1. Install Docker Desktop on Windows

Use the official [Docker Desktop for Windows instructions](https://docs.docker.com/desktop/setup/install/windows-install/). The per-user installation with the WSL 2 backend is appropriate for this local portfolio project.

If Windows reports that WSL is missing or outdated, open PowerShell as Administrator and run:

```powershell
wsl --install
wsl --update
```

Restart Windows if prompted. Open Docker Desktop and wait until it reports that the Docker engine is running. Keep Linux containers selected.

Verify the installation in a new VS Code PowerShell terminal:

```powershell
docker --version
docker compose version
```

Both commands must return version information before continuing.

## 2. Prepare the project

Open this folder in VS Code:

```text
C:\Users\brend\OneDrive\baseball-video-scouting
```

Stop locally running Vite and FastAPI terminals with `Ctrl+C` so ports 5173 and 8000 are available. Your existing Windows PostgreSQL server can remain running because Docker publishes its separate database on host port 5433.

Make sure the cleaned dataset is located here:

```text
data\processed\Messick_cleaned.csv
```

If the file has a different name, either rename it or set `CLEANED_DATASET` to that filename in the next step.

## 3. Create the private Docker environment file

From the repository root:

```powershell
Copy-Item .env.docker.example .env.docker
code .env.docker
```

Change this placeholder to a new password used only for the local Docker database:

```text
POSTGRES_PASSWORD=replace_with_a_local_docker_password
```

Use letters and numbers for the first local setup. Do not use your Windows PostgreSQL password, and do not commit `.env.docker`.

The default ports are:

| Service | Host address | Container port |
| --- | --- | --- |
| React/Nginx | `127.0.0.1:5173` | `80` |
| FastAPI | `127.0.0.1:8000` | `8000` |
| PostgreSQL | `127.0.0.1:5433` | `5432` |

## 4. Validate the configuration

```powershell
docker compose --env-file .env.docker config
```

This checks Compose interpolation and displays the resolved configuration. Do not post the output publicly because it contains the local Docker password.

## 5. Start everything with one command

```powershell
docker compose --env-file .env.docker up --build
```

The first build can take several minutes because Docker downloads the base images and installs Python and JavaScript packages. Leave this terminal open.

The `data-loader` container is supposed to finish with exit code 0. It is a one-time startup task, not a server that remains running.

Open:

- React application: [http://127.0.0.1:5173](http://127.0.0.1:5173)
- FastAPI health check: [http://127.0.0.1:8000/health](http://127.0.0.1:8000/health)
- FastAPI Swagger page: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)

The health response should report `baseball_video_scouting`. The application should list Parker Messick if the cleaned CSV was found and loaded.

## 6. Inspect containers and logs

Open another PowerShell terminal in the repository root:

```powershell
docker compose --env-file .env.docker ps
docker compose --env-file .env.docker logs data-loader
docker compose --env-file .env.docker logs backend
```

Follow all running logs with:

```powershell
docker compose --env-file .env.docker logs -f
```

Press `Ctrl+C` to stop following detached logs; it does not delete containers.

## 7. Stop and restart

When `docker compose up` is attached to the terminal, press `Ctrl+C`. You can also stop and remove the containers from another terminal:

```powershell
docker compose --env-file .env.docker down
```

This preserves the PostgreSQL named volume. Start the application again with:

```powershell
docker compose --env-file .env.docker up --build
```

To run everything in the background instead:

```powershell
docker compose --env-file .env.docker up --build -d
```

## Troubleshooting

### The application has no pitchers

Check the loader:

```powershell
docker compose --env-file .env.docker logs data-loader
```

If it says the cleaned dataset was not found, put the file in `data\processed`, confirm `CLEANED_DATASET` matches the filename exactly, and rerun:

```powershell
docker compose --env-file .env.docker up --build
```

The loader uses upserts, so rerunning it does not duplicate pitch IDs.

### Port 5173 or 8000 is already in use

Stop the old Vite or FastAPI terminal with `Ctrl+C`. Alternatively, change `FRONTEND_PORT` or `BACKEND_PORT` in `.env.docker` and open the new port afterward.

### Port 5433 is already in use

Change `POSTGRES_HOST_PORT` in `.env.docker`. Internal containers still communicate over port 5432.

### The Docker password was changed after the first startup

PostgreSQL reads `POSTGRES_PASSWORD` only when it initializes a new data directory. Either restore the original value or reset the Docker-only database volume.

The following command permanently deletes the PostgreSQL data stored by this Docker Compose project. It does not delete the separate PostgreSQL installation on Windows:

```powershell
docker compose --env-file .env.docker down -v
```

Only run it when you intentionally want a clean Docker database. The next `up --build` recreates the schema and reloads the cleaned CSV.
