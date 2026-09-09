"""Playlist creation and pitch membership routes."""

from typing import Annotated

import psycopg
from fastapi import APIRouter, Depends, HTTPException, Path, Response, status

from app.database import get_db
from app.schemas.common import PITCH_ID_PATTERN
from app.schemas.playlists import PlaylistCreate, PlaylistItemsSave, PlaylistPitchCreate
from app.services.deployment import require_playlist_write_access

router = APIRouter(
    prefix="/playlists",
    tags=["playlists"],
    dependencies=[Depends(require_playlist_write_access)],
)


PLAYLIST_ITEM_SELECT = """
    SELECT
        item.display_order,
        item.scouting_note,
        p.*,
        pitcher.player_name AS pitcher_name,
        batter.player_name AS batter_name,
        g.game_date,
        g.home_team,
        g.away_team,
        v.video_url,
        COALESCE(v.video_available, FALSE) AS video_available
    FROM playlist_items AS item
    JOIN pitches AS p ON p.pitch_id = item.pitch_id
    JOIN games AS g ON g.game_pk = p.game_pk
    JOIN players AS pitcher ON pitcher.player_id = p.pitcher_id
    LEFT JOIN players AS batter ON batter.player_id = p.batter_id
    LEFT JOIN videos AS v ON v.pitch_id = p.pitch_id
    WHERE item.playlist_id = %s
    ORDER BY item.display_order
"""


def _require_playlist(connection: psycopg.Connection, playlist_id: int) -> dict:
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT playlist_id, playlist_name, description, created_at
            FROM playlists
            WHERE playlist_id = %s
            """,
            (playlist_id,),
        )
        playlist = cursor.fetchone()

    if playlist is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Playlist {playlist_id} was not found.",
        )
    return playlist


@router.get("")
def list_playlists(
    connection: psycopg.Connection = Depends(get_db),
) -> list[dict]:
    """List saved playlists with item and video counts."""
    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT
                playlist.playlist_id,
                playlist.playlist_name,
                playlist.description,
                playlist.created_at,
                COUNT(item.pitch_id)::integer AS item_count,
                COUNT(item.pitch_id) FILTER (
                    WHERE COALESCE(video.video_available, FALSE)
                )::integer AS video_count
            FROM playlists AS playlist
            LEFT JOIN playlist_items AS item
                ON item.playlist_id = playlist.playlist_id
            LEFT JOIN videos AS video ON video.pitch_id = item.pitch_id
            GROUP BY playlist.playlist_id
            ORDER BY playlist.created_at DESC, playlist.playlist_id DESC
            """)
        return cursor.fetchall()


@router.post("", status_code=status.HTTP_201_CREATED)
def create_playlist(
    body: PlaylistCreate,
    connection: psycopg.Connection = Depends(get_db),
) -> dict:
    with connection.cursor() as cursor:
        cursor.execute(
            """
            INSERT INTO playlists (playlist_name, description)
            VALUES (%s, %s)
            RETURNING playlist_id, playlist_name, description, created_at
            """,
            (body.playlist_name, body.description),
        )
        return cursor.fetchone()


@router.put("/{playlist_id}")
def update_playlist(
    playlist_id: Annotated[int, Path(gt=0)],
    body: PlaylistCreate,
    connection: psycopg.Connection = Depends(get_db),
) -> dict:
    _require_playlist(connection, playlist_id)

    with connection.cursor() as cursor:
        cursor.execute(
            """
            UPDATE playlists
            SET playlist_name = %s, description = %s
            WHERE playlist_id = %s
            RETURNING playlist_id, playlist_name, description, created_at
            """,
            (body.playlist_name, body.description, playlist_id),
        )
        return cursor.fetchone()


@router.post("/{playlist_id}/pitches", status_code=status.HTTP_201_CREATED)
def add_pitch_to_playlist(
    playlist_id: Annotated[int, Path(gt=0)],
    body: PlaylistPitchCreate,
    connection: psycopg.Connection = Depends(get_db),
) -> dict:
    _require_playlist(connection, playlist_id)

    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT 1 FROM pitches WHERE pitch_id = %s",
            (body.pitch_id,),
        )
        if cursor.fetchone() is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Pitch {body.pitch_id} was not found.",
            )

        cursor.execute(
            """
            SELECT display_order
            FROM playlist_items
            WHERE playlist_id = %s AND pitch_id = %s
            """,
            (playlist_id, body.pitch_id),
        )
        existing_item = cursor.fetchone()

        display_order = body.display_order
        if display_order is None and existing_item is not None:
            display_order = existing_item["display_order"]
        elif display_order is None:
            cursor.execute(
                """
                SELECT COALESCE(MAX(display_order), 0) + 1 AS next_order
                FROM playlist_items
                WHERE playlist_id = %s
                """,
                (playlist_id,),
            )
            display_order = cursor.fetchone()["next_order"]

        cursor.execute(
            """
            SELECT pitch_id
            FROM playlist_items
            WHERE playlist_id = %s
              AND display_order = %s
              AND pitch_id <> %s
            """,
            (playlist_id, display_order, body.pitch_id),
        )
        order_conflict = cursor.fetchone()
        if order_conflict is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    f"Display order {display_order} is already used by pitch "
                    f"{order_conflict['pitch_id']}."
                ),
            )

        cursor.execute(
            """
            INSERT INTO playlist_items (
                playlist_id,
                pitch_id,
                display_order,
                scouting_note
            )
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (playlist_id, pitch_id)
            DO UPDATE SET
                display_order = EXCLUDED.display_order,
                scouting_note = EXCLUDED.scouting_note
            RETURNING playlist_id, pitch_id, display_order, scouting_note
            """,
            (
                playlist_id,
                body.pitch_id,
                display_order,
                body.scouting_note,
            ),
        )
        return cursor.fetchone()


@router.put("/{playlist_id}/items")
def save_playlist_items(
    playlist_id: Annotated[int, Path(gt=0)],
    body: PlaylistItemsSave,
    connection: psycopg.Connection = Depends(get_db),
) -> dict:
    """Atomically replace a playlist's complete ordered pitch list."""
    _require_playlist(connection, playlist_id)
    pitch_ids = [item.pitch_id for item in body.items]

    with connection.cursor() as cursor:
        if pitch_ids:
            cursor.execute(
                "SELECT pitch_id FROM pitches WHERE pitch_id = ANY(%s)",
                (pitch_ids,),
            )
            found_pitch_ids = {row["pitch_id"] for row in cursor.fetchall()}
            missing_pitch_ids = [
                pitch_id for pitch_id in pitch_ids if pitch_id not in found_pitch_ids
            ]
            if missing_pitch_ids:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=(
                        "The following pitches were not found: " + ", ".join(missing_pitch_ids)
                    ),
                )

        cursor.execute(
            "DELETE FROM playlist_items WHERE playlist_id = %s",
            (playlist_id,),
        )

        if body.items:
            cursor.executemany(
                """
                INSERT INTO playlist_items (
                    playlist_id,
                    pitch_id,
                    display_order,
                    scouting_note
                )
                VALUES (%s, %s, %s, %s)
                """,
                [
                    (
                        playlist_id,
                        item.pitch_id,
                        display_order,
                        item.scouting_note,
                    )
                    for display_order, item in enumerate(body.items, start=1)
                ],
            )

    return get_playlist(playlist_id, connection)


@router.get("/{playlist_id}")
def get_playlist(
    playlist_id: Annotated[int, Path(gt=0)],
    connection: psycopg.Connection = Depends(get_db),
) -> dict:
    playlist = _require_playlist(connection, playlist_id)

    with connection.cursor() as cursor:
        cursor.execute(PLAYLIST_ITEM_SELECT, (playlist_id,))
        items = cursor.fetchall()

    return {**playlist, "items": items}


@router.delete(
    "/{playlist_id}/pitches/{pitch_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def remove_pitch_from_playlist(
    playlist_id: Annotated[int, Path(gt=0)],
    pitch_id: Annotated[
        str,
        Path(min_length=5, max_length=100, pattern=PITCH_ID_PATTERN),
    ],
    connection: psycopg.Connection = Depends(get_db),
) -> Response:
    _require_playlist(connection, playlist_id)

    with connection.cursor() as cursor:
        cursor.execute(
            """
            DELETE FROM playlist_items
            WHERE playlist_id = %s AND pitch_id = %s
            RETURNING pitch_id
            """,
            (playlist_id, pitch_id),
        )
        deleted = cursor.fetchone()

    if deleted is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Pitch {pitch_id} is not in playlist {playlist_id}.",
        )

    with connection.cursor() as cursor:
        cursor.execute(
            """
            WITH reordered AS (
                SELECT
                    pitch_id,
                    ROW_NUMBER() OVER (ORDER BY display_order)::integer AS new_order
                FROM playlist_items
                WHERE playlist_id = %s
            )
            UPDATE playlist_items AS item
            SET display_order = reordered.new_order
            FROM reordered
            WHERE item.playlist_id = %s
              AND item.pitch_id = reordered.pitch_id
            """,
            (playlist_id, playlist_id),
        )
    return Response(status_code=status.HTTP_204_NO_CONTENT)
