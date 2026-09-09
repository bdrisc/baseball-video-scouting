"""PostgreSQL connection dependency used by the API routers."""

import json
import os
from collections.abc import Generator
from functools import lru_cache
from pathlib import Path

import boto3
import psycopg
from botocore.exceptions import BotoCoreError, ClientError
from dotenv import load_dotenv
from fastapi import HTTPException, status
from psycopg.rows import dict_row

ENV_FILE = Path(__file__).resolve().parents[1] / ".env"
load_dotenv(ENV_FILE)


class DatabaseConfigurationError(RuntimeError):
    """Raised when cloud database credentials cannot be loaded safely."""


@lru_cache(maxsize=1)
def get_database_url() -> str | None:
    """Retrieve the cloud database URL once per running process."""
    secret_arn = os.getenv("DB_SECRET_ARN", "").strip()

    if not secret_arn:
        return os.getenv("DATABASE_URL", "").strip() or None

    try:
        response = boto3.client("secretsmanager").get_secret_value(SecretId=secret_arn)
        secret_payload = json.loads(response["SecretString"])
    except (
        BotoCoreError,
        ClientError,
        KeyError,
        TypeError,
        json.JSONDecodeError,
    ) as exc:
        raise DatabaseConfigurationError("The database secret could not be retrieved.") from exc

    if not isinstance(secret_payload, dict):
        raise DatabaseConfigurationError("The database secret must contain a JSON object.")

    database_url = str(secret_payload.get("DATABASE_URL", "")).strip()

    if not database_url:
        raise DatabaseConfigurationError("The database secret does not contain DATABASE_URL.")

    return database_url


def get_connection() -> psycopg.Connection:
    """Open a PostgreSQL connection that returns rows as dictionaries."""
    database_url = get_database_url()

    if database_url:
        return psycopg.connect(
            database_url,
            connect_timeout=10,
            row_factory=dict_row,
        )

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
    except (
        psycopg.OperationalError,
        DatabaseConfigurationError,
    ) as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="The API could not connect to PostgreSQL.",
        ) from exc
