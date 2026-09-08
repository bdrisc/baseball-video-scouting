"""FastAPI entry point for the baseball video scouting API."""

import os

from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.routers import health, pitchers, pitches, playlists

app = FastAPI(
    title="Baseball Video Scouting API",
    description=(
        "Pitch-level Statcast data, official MLB video links, and scouting "
        "playlists backed by PostgreSQL."
    ),
    version="0.1.0",
)

frontend_origins = [
    origin.strip()
    for origin in os.getenv(
        "FRONTEND_ORIGINS",
        "http://localhost:5173,http://127.0.0.1:5173",
    ).split(",")
    if origin.strip()
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=frontend_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(pitchers.router)
app.include_router(pitches.router)
app.include_router(playlists.router)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(
    _request: Request,
    exception: RequestValidationError,
) -> JSONResponse:
    """Return concise, field-specific details for invalid API inputs."""
    details = []
    for error in exception.errors():
        detail = {
            "field": ".".join(str(part) for part in error["loc"]),
            "message": error["msg"],
            "type": error["type"],
        }
        submitted_value = error.get("input")
        if submitted_value is None or isinstance(
            submitted_value,
            (str, int, float, bool),
        ):
            detail["submitted_value"] = submitted_value
        details.append(detail)

    return JSONResponse(
        status_code=422,
        content=jsonable_encoder(
            {
                "error": "validation_error",
                "message": "One or more request values are invalid.",
                "details": details,
            }
        ),
    )


@app.get("/", tags=["health"])
def root() -> dict[str, str]:
    return {
        "message": "Baseball Video Scouting API",
        "documentation": "/docs",
    }
