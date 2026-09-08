"""Existence checks shared by multiple route modules."""

import psycopg
from fastapi import HTTPException, status


def require_pitcher(connection: psycopg.Connection, pitcher_id: int) -> dict:
    """Return a pitcher or raise a clear 404 response."""
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT pl.player_id, pl.mlb_id, pl.player_name, pl.throws, pl.bats
            FROM players AS pl
            WHERE pl.player_id = %s
              AND EXISTS (
                  SELECT 1
                  FROM pitches AS p
                  WHERE p.pitcher_id = pl.player_id
              )
            """,
            (pitcher_id,),
        )
        pitcher = cursor.fetchone()

    if pitcher is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Pitcher {pitcher_id} was not found.",
        )
    return pitcher


def require_game(connection: psycopg.Connection, game_pk: int) -> None:
    """Raise a clear 404 response when a requested game does not exist."""
    with connection.cursor() as cursor:
        cursor.execute("SELECT 1 FROM games WHERE game_pk = %s", (game_pk,))
        exists = cursor.fetchone()

    if exists is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Game {game_pk} was not found.",
        )
