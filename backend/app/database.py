"""PostgreSQL connection dependency used by the API routers."""

import os
from collections.abc import Generator
from pathlib import Path

import psycopg
from dotenv import load_dotenv
from fastapi import HTTPException, status
from psycopg.rows import dict_row

ENV_FILE = Path(__file__).resolve().parents[1] / ".env"
load_dotenv(ENV_FILE)


def get_connection() -> psycopg.Connection:
    """Open a PostgreSQL connection that returns rows as dictionaries."""
    return psycopg.connect(
        host=os.getenv("DB_HOST", "localhost"),
        port=int(os.getenv("DB_PORT", "5432")),
        dbname=os.getenv("DB_NAME", "baseball_video_scouting"),
        user=os.getenv("DB_USER", "postgres"),
        password=os.getenv("DB_PASSWORD", ""),
        connect_timeout=5,
        row_factory=dict_row,
    )


def get_db() -> Generator[psycopg.Connection, None, None]:
    """Yield one transaction-scoped connection per request."""
    try:
        with get_connection() as connection:
            yield connection
    except psycopg.OperationalError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="The API could not connect to PostgreSQL.",
        ) from exc
