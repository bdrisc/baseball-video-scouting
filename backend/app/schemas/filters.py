"""Validated query-parameter models for pitch searches."""

from datetime import date
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.schemas.common import BatterSide, PitchType


class PitchSortField(str, Enum):
    """Public, allowlisted columns supported by GET /pitches sorting."""

    GAME_DATE = "game_date"
    BATTER_NAME = "batter_name"
    PITCH_TYPE = "pitch_type"
    VELOCITY = "velocity"
    SPIN_RATE = "spin_rate"
    INNING = "inning"
    RESULT = "result"


class SortOrder(str, Enum):
    ASCENDING = "asc"
    DESCENDING = "desc"


class PitchFilterCriteria(BaseModel):
    """Filters shared by pitch rows and full-result aggregate summaries."""

    model_config = ConfigDict(extra="forbid")

    pitcher_id: int | None = Field(default=None, gt=0)
    game_pk: int | None = Field(default=None, gt=0)
    pitch_type: PitchType | None = None
    balls: int | None = Field(default=None, ge=0, le=3)
    strikes: int | None = Field(default=None, ge=0, le=2)
    batter_side: BatterSide | None = None
    result: str | None = Field(default=None, min_length=1, max_length=100)
    start_date: date | None = None
    end_date: date | None = None
    min_velocity: float | None = Field(default=None, ge=0, le=110)
    max_velocity: float | None = Field(default=None, ge=0, le=110)
    min_plate_x: float | None = Field(default=None, ge=-5, le=5)
    max_plate_x: float | None = Field(default=None, ge=-5, le=5)
    min_plate_z: float | None = Field(default=None, ge=-2, le=8)
    max_plate_z: float | None = Field(default=None, ge=-2, le=8)
    video_available: bool | None = None

    @field_validator("pitch_type", mode="before")
    @classmethod
    def normalize_pitch_type(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip().upper()
        return value

    @field_validator("batter_side", mode="before")
    @classmethod
    def normalize_batter_side(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip().upper()
        return value

    @field_validator("result")
    @classmethod
    def normalize_result(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        if not value:
            raise ValueError("result cannot be blank")
        return value

    @model_validator(mode="after")
    def validate_ranges(self) -> "PitchFilterCriteria":
        pairs = (
            ("min_velocity", self.min_velocity, "max_velocity", self.max_velocity),
            ("min_plate_x", self.min_plate_x, "max_plate_x", self.max_plate_x),
            ("min_plate_z", self.min_plate_z, "max_plate_z", self.max_plate_z),
        )
        for minimum_name, minimum, maximum_name, maximum in pairs:
            if minimum is not None and maximum is not None and minimum > maximum:
                raise ValueError(f"{minimum_name} cannot exceed {maximum_name}")

        if (
            self.start_date is not None
            and self.end_date is not None
            and self.start_date > self.end_date
        ):
            raise ValueError("start_date cannot be after end_date")

        return self


class PitchAggregateFilters(PitchFilterCriteria):
    """Validated filters for GET /pitches/aggregates."""


class PitchFilters(PitchFilterCriteria):
    """Validated filters, pagination, and sorting for GET /pitches."""

    limit: int = Field(default=100, ge=1, le=500)
    offset: int = Field(default=0, ge=0)
    sort_by: PitchSortField = PitchSortField.GAME_DATE
    sort_order: SortOrder = SortOrder.ASCENDING

    @field_validator("sort_by", "sort_order", mode="before")
    @classmethod
    def normalize_sort_value(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip().lower()
        return value
