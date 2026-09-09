"""Deployment-specific API safeguards."""

import os

from fastapi import HTTPException, Request, status

WRITE_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})
TRUE_VALUES = frozenset({"1", "true", "yes", "on"})


def is_read_only_mode() -> bool:
    """Return whether mutating public API routes are disabled."""
    return os.getenv("READ_ONLY_MODE", "false").strip().lower() in TRUE_VALUES


def require_playlist_write_access(request: Request) -> None:
    """Block playlist mutations in the unauthenticated public deployment."""
    if request.method.upper() in WRITE_METHODS and is_read_only_mode():
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                "Playlist saving is disabled in the public portfolio demo. "
                "The complete playlist workflow remains available locally."
            ),
        )
