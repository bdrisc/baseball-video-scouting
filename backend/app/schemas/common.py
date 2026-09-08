"""Shared constrained types and enumerations used by request models."""

from enum import Enum
from typing import Annotated

from pydantic import StringConstraints

PITCH_ID_PATTERN = r"^\d+_\d+_\d+$"

PitchId = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True,
        min_length=5,
        max_length=100,
        pattern=PITCH_ID_PATTERN,
    ),
]


class PitchType(str, Enum):
    """Pitch codes used by MLB Statcast/Savant."""

    CHANGEUP = "CH"
    SLOW_CURVE = "CS"
    CURVEBALL = "CU"
    EEPHUS = "EP"
    FOUR_SEAM_FASTBALL = "FF"
    OTHER_FASTBALL = "FA"
    CUTTER = "FC"
    FORKBALL = "FO"
    SPLITTER = "FS"
    KNUCKLE_CURVE = "KC"
    KNUCKLEBALL = "KN"
    PITCHOUT = "PO"
    SCREWBALL = "SC"
    SINKER = "SI"
    SLIDER = "SL"
    SWEEPER = "ST"
    SLURVE = "SV"


class BatterSide(str, Enum):
    LEFT = "L"
    RIGHT = "R"
