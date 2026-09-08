"""Tests for playlist creation, ordered saves, notes, and removal."""

from __future__ import annotations

from app.routers.playlists import (
    add_pitch_to_playlist,
    create_playlist,
    remove_pitch_from_playlist,
    save_playlist_items,
)
from app.schemas.playlists import (
    PlaylistCreate,
    PlaylistItemSave,
    PlaylistItemsSave,
    PlaylistPitchCreate,
)

PLAYLIST = {
    "playlist_id": 3,
    "playlist_name": "Two-strike breaking balls",
    "description": "Finish-pitch review",
    "created_at": "2026-09-07T12:00:00-04:00",
}


def test_create_playlist_uses_parameterized_insert(scripted_connection_factory) -> None:
    connection = scripted_connection_factory([PLAYLIST])

    result = create_playlist(
        PlaylistCreate(
            playlist_name="Two-strike breaking balls",
            description="Finish-pitch review",
        ),
        connection,
    )

    assert result["playlist_id"] == 3
    assert "VALUES (%s, %s)" in connection.calls[0].query
    assert connection.calls[0].parameters == (
        "Two-strike breaking balls",
        "Finish-pitch review",
    )


def test_add_pitch_assigns_next_order_and_preserves_note(
    scripted_connection_factory,
) -> None:
    saved_item = {
        "playlist_id": 3,
        "pitch_id": "824566_10_5",
        "display_order": 2,
        "scouting_note": "Slider below the zone for a whiff.",
    }
    connection = scripted_connection_factory(
        [
            PLAYLIST,
            {"exists": 1},
            None,
            {"next_order": 2},
            None,
            saved_item,
        ]
    )

    result = add_pitch_to_playlist(
        3,
        PlaylistPitchCreate(
            pitch_id="824566_10_5",
            scouting_note="Slider below the zone for a whiff.",
        ),
        connection,
    )

    insert_call = connection.calls[-1]
    assert result == saved_item
    assert "ON CONFLICT (playlist_id, pitch_id)" in insert_call.query
    assert insert_call.parameters == (
        3,
        "824566_10_5",
        2,
        "Slider below the zone for a whiff.",
    )


def test_bulk_save_writes_display_order_and_notes_atomically(
    scripted_connection_factory,
) -> None:
    items = [
        {
            "display_order": 1,
            "pitch_id": "824566_8_1",
            "scouting_note": "Elevated fastball.",
        },
        {
            "display_order": 2,
            "pitch_id": "824566_10_5",
            "scouting_note": "Slider chase.",
        },
    ]
    connection = scripted_connection_factory(
        [
            PLAYLIST,
            [{"pitch_id": "824566_8_1"}, {"pitch_id": "824566_10_5"}],
            None,
            None,
            PLAYLIST,
            items,
        ]
    )
    body = PlaylistItemsSave(
        items=[
            PlaylistItemSave(pitch_id="824566_8_1", scouting_note="Elevated fastball."),
            PlaylistItemSave(pitch_id="824566_10_5", scouting_note="Slider chase."),
        ]
    )

    result = save_playlist_items(3, body, connection)

    bulk_call = next(call for call in connection.calls if call.operation == "executemany")
    assert bulk_call.parameters == [
        (3, "824566_8_1", 1, "Elevated fastball."),
        (3, "824566_10_5", 2, "Slider chase."),
    ]
    assert [item["pitch_id"] for item in result["items"]] == [
        "824566_8_1",
        "824566_10_5",
    ]


def test_remove_pitch_then_reorders_remaining_items(
    scripted_connection_factory,
) -> None:
    connection = scripted_connection_factory([PLAYLIST, {"pitch_id": "824566_8_1"}, None])

    response = remove_pitch_from_playlist(3, "824566_8_1", connection)

    assert response.status_code == 204
    delete_call = connection.calls[1]
    reorder_call = connection.calls[2]
    assert "DELETE FROM playlist_items" in delete_call.query
    assert delete_call.parameters == (3, "824566_8_1")
    assert "ROW_NUMBER() OVER" in reorder_call.query
    assert reorder_call.parameters == (3, 3)
