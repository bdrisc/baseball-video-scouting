"""Health-check route."""

import psycopg
from fastapi import APIRouter, Depends

from app.database import get_db

router = APIRouter(tags=["health"])


@router.get("/health")
def health(connection: psycopg.Connection = Depends(get_db)) -> dict:
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT
                current_database() AS database,
                CURRENT_TIMESTAMP AS checked_at
            """
        )
        database_status = cursor.fetchone()

    return {"status": "ok", **database_status}
