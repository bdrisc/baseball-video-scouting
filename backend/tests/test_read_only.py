"""Tests for public portfolio write protection."""

import pytest
from app.services.deployment import require_playlist_write_access
from fastapi import HTTPException
from starlette.requests import Request


def make_request(method: str) -> Request:
    """Create a minimal HTTP request for dependency testing."""
    return Request(
        {
            "type": "http",
            "method": method,
            "path": "/playlists",
            "headers": [],
        }
    )


def test_read_only_mode_blocks_playlist_writes(monkeypatch) -> None:
    monkeypatch.setenv("READ_ONLY_MODE", "true")

    with pytest.raises(HTTPException) as exception:
        require_playlist_write_access(make_request("POST"))

    assert exception.value.status_code == 403
    assert "public portfolio demo" in exception.value.detail


def test_read_only_mode_allows_playlist_reads(monkeypatch) -> None:
    monkeypatch.setenv("READ_ONLY_MODE", "true")

    assert require_playlist_write_access(make_request("GET")) is None
