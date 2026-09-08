"""Validated request models for playlist operations."""

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.schemas.common import PitchId


class PlaylistCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    playlist_name: str = Field(min_length=1, max_length=100)
    description: str | None = Field(default=None, max_length=1000)

    @field_validator("playlist_name")
    @classmethod
    def name_must_not_be_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("playlist_name cannot be blank")
        return value

    @field_validator("description")
    @classmethod
    def normalize_description(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return value.strip() or None


class PlaylistPitchCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    pitch_id: PitchId
    display_order: int | None = Field(default=None, ge=1)
    scouting_note: str | None = Field(default=None, max_length=2000)

    @field_validator("scouting_note")
    @classmethod
    def normalize_scouting_note(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return value.strip() or None


class PlaylistItemSave(BaseModel):
    """One item in a complete ordered playlist save."""

    model_config = ConfigDict(str_strip_whitespace=True)

    pitch_id: PitchId
    scouting_note: str | None = Field(default=None, max_length=2000)

    @field_validator("scouting_note")
    @classmethod
    def normalize_scouting_note(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return value.strip() or None


class PlaylistItemsSave(BaseModel):
    """Complete ordered contents supplied by the playlist editor."""

    items: list[PlaylistItemSave] = Field(default_factory=list, max_length=500)

    @model_validator(mode="after")
    def pitch_ids_must_be_unique(self) -> "PlaylistItemsSave":
        pitch_ids = [item.pitch_id for item in self.items]
        if len(pitch_ids) != len(set(pitch_ids)):
            raise ValueError("A pitch can appear only once in a playlist.")
        return self
