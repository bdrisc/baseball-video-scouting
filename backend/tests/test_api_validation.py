"""HTTP-level tests for clear Pydantic and not-found responses."""

from __future__ import annotations

import pytest
from app.database import get_db
from app.main import app
from fastapi.testclient import TestClient


@pytest.fixture
def client(scripted_connection_factory):
    connection = scripted_connection_factory()

    def override_database():
        yield connection

    app.dependency_overrides[get_db] = override_database
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.mark.parametrize(
    ("url", "expected_field"),
    [
        ("/pitches?pitch_type=NOT_A_PITCH", "query.pitch_type"),
        ("/pitches?balls=4", "query.balls"),
        ("/pitches?min_velocity=96&max_velocity=90", "query"),
        ("/pitches?start_date=2026-08-31&end_date=2026-08-01", "query"),
        ("/pitches/not-a-pitch-id", "path.pitch_id"),
    ],
)
def test_invalid_requests_return_structured_422(
    client: TestClient, url: str, expected_field: str
) -> None:
    response = client.get(url)

    assert response.status_code == 422
    body = response.json()
    assert body["error"] == "validation_error"
    assert any(detail["field"].startswith(expected_field) for detail in body["details"])


def test_blank_playlist_name_returns_422(client: TestClient) -> None:
    response = client.post(
        "/playlists",
        json={"playlist_name": "   ", "description": None},
    )

    assert response.status_code == 422
    assert response.json()["error"] == "validation_error"


def test_scouting_note_length_is_validated(client: TestClient) -> None:
    response = client.post(
        "/playlists/1/pitches",
        json={
            "pitch_id": "824566_8_1",
            "scouting_note": "x" * 2001,
        },
    )

    assert response.status_code == 422
    assert any(item["field"] == "body.scouting_note" for item in response.json()["details"])


def test_nonexistent_pitcher_returns_clear_404(
    scripted_connection_factory,
) -> None:
    connection = scripted_connection_factory([None])

    def override_database():
        yield connection

    app.dependency_overrides[get_db] = override_database
    try:
        with TestClient(app) as test_client:
            response = test_client.get("/pitches?pitcher_id=999")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 404
    assert response.json() == {"detail": "Pitcher 999 was not found."}
