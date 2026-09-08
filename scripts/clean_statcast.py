#!/usr/bin/env python3
"""Build a clean, video-linked Baseball Savant pitch dataset.

The pipeline keeps one row per pitch, creates and validates a stable ``pitch_id``,
standardizes pitch names, adds scouting-friendly features, and joins video URLs
by ``pitch_id`` (never by row position).

Example
-------
python scripts/clean_statcast.py \
    --savant-csv data/raw/Messick_Data_with_ids.csv \
    --video-table data/raw/Messick_video_links.xlsx \
    --output data/processed/Messick_cleaned.csv \
    --require-all-video

Missing-value policy
--------------------
* Pitch identifiers and count fields are required; missing values stop the run.
* Missing categorical outcomes are labeled ``none`` or ``unknown``.
* Missing measurements remain blank. They are not replaced with zero because
  zero is a meaningful measurement.
* Missing video fields remain blank and are represented by ``has_video=False``.
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Iterable

import pandas as pd

PITCH_NAME_MAP = {
    "FF": "Four-Seam Fastball",
    "SI": "Sinker",
    "FC": "Cutter",
    "CH": "Changeup",
    "FS": "Split-Finger",
    "FO": "Forkball",
    "SC": "Screwball",
    "SL": "Slider",
    "ST": "Sweeper",
    "SV": "Slurve",
    "CU": "Curveball",
    "KC": "Knuckle Curve",
    "CS": "Slow Curve",
    "KN": "Knuckleball",
    "EP": "Eephus",
    "PO": "Pitchout",
}

CORE_COLUMNS = [
    "game_date",
    "game_pk",
    "at_bat_number",
    "pitch_number",
    "pitch_type",
    "description",
    "balls",
    "strikes",
    "zone",
    "plate_x",
    "plate_z",
    "sz_top",
    "sz_bot",
    "n_thruorder_pitcher",
]

# Optional columns are added as blanks when an older Savant export omits them.
# This produces a predictable output schema without inventing numeric values.
SELECTED_COLUMNS = [
    "game_date",
    "game_pk",
    "game_type",
    "at_bat_number",
    "pitch_number",
    "inning",
    "inning_topbot",
    "outs_when_up",
    "home_team",
    "away_team",
    "player_name",
    "pitcher",
    "batter",
    "stand",
    "p_throws",
    "balls",
    "strikes",
    "pitch_type",
    "pitch_name",
    "description",
    "events",
    "type",
    "bb_type",
    "zone",
    "release_speed",
    "effective_speed",
    "release_spin_rate",
    "release_extension",
    "release_pos_x",
    "release_pos_y",
    "release_pos_z",
    "pfx_x",
    "pfx_z",
    "plate_x",
    "plate_z",
    "sz_top",
    "sz_bot",
    "arm_angle",
    "launch_speed",
    "launch_angle",
    "hit_distance_sc",
    "estimated_ba_using_speedangle",
    "estimated_woba_using_speedangle",
    "woba_value",
    "delta_run_exp",
    "bat_speed",
    "swing_length",
    "home_score",
    "away_score",
    "bat_score",
    "fld_score",
    "n_thruorder_pitcher",
]

INTEGER_COLUMNS = [
    "game_pk",
    "at_bat_number",
    "pitch_number",
    "inning",
    "outs_when_up",
    "pitcher",
    "batter",
    "balls",
    "strikes",
    "zone",
    "home_score",
    "away_score",
    "bat_score",
    "fld_score",
    "n_thruorder_pitcher",
]

FLOAT_COLUMNS = [
    "release_speed",
    "effective_speed",
    "release_spin_rate",
    "release_extension",
    "release_pos_x",
    "release_pos_y",
    "release_pos_z",
    "pfx_x",
    "pfx_z",
    "plate_x",
    "plate_z",
    "sz_top",
    "sz_bot",
    "arm_angle",
    "launch_speed",
    "launch_angle",
    "hit_distance_sc",
    "estimated_ba_using_speedangle",
    "estimated_woba_using_speedangle",
    "woba_value",
    "delta_run_exp",
    "bat_speed",
    "swing_length",
]

SWING_DESCRIPTIONS = {
    "swinging_strike",
    "swinging_strike_blocked",
    "missed_bunt",
    "foul",
    "foul_tip",
    "foul_bunt",
    "hit_into_play",
}
WHIFF_DESCRIPTIONS = {
    "swinging_strike",
    "swinging_strike_blocked",
    "missed_bunt",
}
CONTACT_DESCRIPTIONS = {
    "foul",
    "foul_tip",
    "foul_bunt",
    "hit_into_play",
}

OUTPUT_COLUMNS = [
    "pitch_id",
    "game_date",
    "game_pk",
    "game_type",
    "at_bat_number",
    "pitch_number",
    "inning",
    "inning_topbot",
    "outs_when_up",
    "home_team",
    "away_team",
    "player_name",
    "pitcher",
    "batter",
    "stand",
    "p_throws",
    "balls",
    "strikes",
    "count",
    "pitcher_advantage_count",
    "is_two_strike",
    "is_first_pitch",
    "times_through_order",
    "pitch_type",
    "pitch_name",
    "pitch_name_raw",
    "description",
    "events",
    "type",
    "bb_type",
    "is_strike",
    "is_swing",
    "is_contact",
    "is_whiff",
    "is_csw",
    "is_in_zone",
    "is_chase",
    "zone",
    "release_speed",
    "effective_speed",
    "release_spin_rate",
    "release_extension",
    "release_pos_x",
    "release_pos_y",
    "release_pos_z",
    "pfx_x",
    "pfx_z",
    "plate_x",
    "plate_z",
    "sz_top",
    "sz_bot",
    "arm_angle",
    "launch_speed",
    "launch_angle",
    "hit_distance_sc",
    "estimated_ba_using_speedangle",
    "estimated_woba_using_speedangle",
    "woba_value",
    "delta_run_exp",
    "bat_speed",
    "swing_length",
    "is_hard_hit",
    "home_score",
    "away_score",
    "bat_score",
    "fld_score",
    "has_video",
    "video_url",
    "video_level",
    "video_notes",
]


def require_columns(frame: pd.DataFrame, columns: Iterable[str], source: str) -> None:
    """Raise a readable error if a source is missing required columns."""
    missing = sorted(set(columns) - set(frame.columns))
    if missing:
        raise ValueError(f"{source} is missing required columns: {', '.join(missing)}")


def clean_text(series: pd.Series, missing_label: str = "") -> pd.Series:
    """Trim text and replace true missing values with a declared label."""
    cleaned = series.astype("string").str.strip()
    return cleaned.fillna(missing_label).replace("", missing_label)


def to_nullable_integer(series: pd.Series) -> pd.Series:
    """Convert numeric-looking input to Pandas' nullable integer type."""
    return pd.to_numeric(series, errors="coerce").round().astype("Int64")


def load_savant(path: Path) -> pd.DataFrame:
    """Extract the Savant CSV and select the project schema."""
    raw = pd.read_csv(path, low_memory=False)
    require_columns(raw, CORE_COLUMNS, "Savant CSV")

    source_pitch_id = None
    if "pitch_id" in raw.columns:
        source_pitch_id = clean_text(raw["pitch_id"])

    selected = raw.reindex(columns=SELECTED_COLUMNS).copy()

    for column in INTEGER_COLUMNS:
        selected[column] = to_nullable_integer(selected[column])
    for column in FLOAT_COLUMNS:
        selected[column] = pd.to_numeric(selected[column], errors="coerce")

    required_non_null = [
        "game_date",
        "game_pk",
        "at_bat_number",
        "pitch_number",
        "pitch_type",
        "description",
        "balls",
        "strikes",
    ]
    null_counts = selected[required_non_null].isna().sum()
    invalid = null_counts[null_counts.gt(0)]
    if not invalid.empty:
        details = ", ".join(f"{name}={count}" for name, count in invalid.items())
        raise ValueError(f"Required Savant values are missing: {details}")

    generated_pitch_id = (
        selected["game_pk"].astype("string")
        + "_"
        + selected["at_bat_number"].astype("string")
        + "_"
        + selected["pitch_number"].astype("string")
    )

    if source_pitch_id is not None:
        comparable = source_pitch_id.ne("")
        mismatched = comparable & source_pitch_id.ne(generated_pitch_id)
        if mismatched.any():
            examples = pd.DataFrame(
                {
                    "source_pitch_id": source_pitch_id[mismatched],
                    "generated_pitch_id": generated_pitch_id[mismatched],
                }
            ).head(5)
            raise ValueError(
                "Existing pitch_id values do not match the generated IDs. "
                f"Examples:\n{examples.to_string(index=False)}"
            )

    selected.insert(0, "pitch_id", generated_pitch_id)
    if selected["pitch_id"].duplicated().any():
        examples = selected.loc[selected["pitch_id"].duplicated(keep=False), "pitch_id"].head(10)
        raise ValueError(
            "The generated pitch_id is not unique. Duplicate examples: " + ", ".join(examples)
        )

    parsed_dates = pd.to_datetime(selected["game_date"], errors="coerce")
    if parsed_dates.isna().any():
        raise ValueError(f"Could not parse {int(parsed_dates.isna().sum())} game_date value(s).")
    selected["game_date"] = parsed_dates.dt.strftime("%Y-%m-%d")

    return selected


def standardize_and_derive(frame: pd.DataFrame) -> pd.DataFrame:
    """Transform pitch fields and add analysis-ready scouting features."""
    data = frame.copy()

    text_defaults = {
        "game_type": "unknown",
        "inning_topbot": "unknown",
        "home_team": "unknown",
        "away_team": "unknown",
        "player_name": "unknown",
        "stand": "unknown",
        "p_throws": "unknown",
        "pitch_type": "unknown",
        "description": "unknown",
        "events": "none",
        "type": "unknown",
        "bb_type": "none",
    }
    for column, label in text_defaults.items():
        data[column] = clean_text(data[column], label)

    data["pitch_name_raw"] = clean_text(data["pitch_name"])
    mapped_name = data["pitch_type"].map(PITCH_NAME_MAP)
    fallback_name = data["pitch_name_raw"].where(data["pitch_name_raw"].ne(""), data["pitch_type"])
    data["pitch_name"] = mapped_name.fillna(fallback_name)

    data["count"] = data["balls"].astype("string") + "-" + data["strikes"].astype("string")
    data["is_two_strike"] = data["strikes"].eq(2)
    data["is_first_pitch"] = data["pitch_number"].eq(1)
    data["pitcher_advantage_count"] = data["balls"].lt(data["strikes"])
    data["times_through_order"] = data["n_thruorder_pitcher"]

    description = data["description"].str.lower()
    data["is_strike"] = data["type"].str.upper().eq("S")
    data["is_swing"] = description.isin(SWING_DESCRIPTIONS)
    data["is_contact"] = description.isin(CONTACT_DESCRIPTIONS)
    data["is_whiff"] = description.isin(WHIFF_DESCRIPTIONS)
    data["is_csw"] = data["is_whiff"] | description.eq("called_strike")

    zone_location_known = data["zone"].notna()
    geometric_location_known = data[["plate_x", "plate_z", "sz_bot", "sz_top"]].notna().all(axis=1)
    in_zone_by_number = data["zone"].between(1, 9, inclusive="both")
    in_zone_by_geometry = (
        data["plate_x"].between(-0.83, 0.83, inclusive="both")
        & data["plate_z"].ge(data["sz_bot"])
        & data["plate_z"].le(data["sz_top"])
    )
    data["is_in_zone"] = in_zone_by_number.where(zone_location_known, in_zone_by_geometry).fillna(
        False
    )
    location_known = zone_location_known | geometric_location_known
    data["is_chase"] = data["is_swing"] & location_known & ~data["is_in_zone"]
    data["is_hard_hit"] = data["launch_speed"].ge(95).fillna(False)

    return data


def load_video_table(path: Path, sheet_name: str) -> pd.DataFrame:
    """Extract and validate the keyed video table."""
    suffix = path.suffix.lower()
    if suffix in {".xlsx", ".xlsm", ".xls"}:
        video = pd.read_excel(path, sheet_name=sheet_name, dtype="string")
    elif suffix in {".csv", ".tsv"}:
        separator = "\t" if suffix == ".tsv" else ","
        video = pd.read_csv(path, sep=separator, dtype="string")
    else:
        raise ValueError("Video table must be an .xlsx, .xlsm, .xls, .csv, or .tsv file.")

    require_columns(video, ["pitch_id", "video_url"], "Video-link table")
    for optional in ["video_level", "video_notes"]:
        if optional not in video.columns:
            video[optional] = ""

    video = video[["pitch_id", "video_url", "video_level", "video_notes"]].copy()
    for column in video.columns:
        video[column] = clean_text(video[column])

    video = video.loc[video["pitch_id"].ne("")].copy()
    if video["pitch_id"].duplicated().any():
        duplicate_ids = video.loc[video["pitch_id"].duplicated(keep=False), "pitch_id"].head(10)
        raise ValueError(
            "Video-link table has duplicate pitch_id values: " + ", ".join(duplicate_ids)
        )

    populated_url = video["video_url"].ne("")
    invalid_url = populated_url & ~video["video_url"].str.startswith(("https://", "http://"))
    if invalid_url.any():
        examples = video.loc[invalid_url, ["pitch_id", "video_url"]].head(5)
        raise ValueError(
            "Video-link table contains invalid URLs. Examples:\n" + examples.to_string(index=False)
        )

    return video


def join_video(pitches: pd.DataFrame, video: pd.DataFrame, require_all_video: bool) -> pd.DataFrame:
    """Join URLs by pitch_id while preserving Savant row order."""
    joined = pitches.merge(
        video,
        on="pitch_id",
        how="left",
        sort=False,
        validate="one_to_one",
        indicator=True,
    )

    # A missing row and a present row with a blank URL both correctly mean no video.
    for column in ["video_url", "video_level", "video_notes"]:
        joined[column] = clean_text(joined[column])
    joined["has_video"] = joined["video_url"].ne("")

    unmatched_video_ids = sorted(set(video["pitch_id"]) - set(pitches["pitch_id"]))
    if unmatched_video_ids:
        print(
            f"Warning: {len(unmatched_video_ids)} video-table pitch_id value(s) "
            "were not found in the Savant CSV."
        )

    missing_video_count = int((~joined["has_video"]).sum())
    if require_all_video and missing_video_count:
        missing_ids = joined.loc[~joined["has_video"], "pitch_id"].head(10)
        raise ValueError(
            f"{missing_video_count} pitch(es) have no video URL. Examples: "
            + ", ".join(missing_ids)
        )

    joined = joined.drop(columns="_merge")
    return joined


def validate_output(frame: pd.DataFrame, expected_rows: int) -> None:
    """Check row grain and logical invariants before loading the CSV."""
    if len(frame) != expected_rows:
        raise ValueError(f"Row count changed from {expected_rows} to {len(frame)}.")
    if frame["pitch_id"].isna().any() or frame["pitch_id"].duplicated().any():
        raise ValueError("Output must contain one unique, non-missing pitch_id per row.")
    if (frame["is_whiff"] & ~frame["is_swing"]).any():
        raise ValueError("Feature invariant failed: every whiff must be a swing.")
    if (frame["is_chase"] & (~frame["is_swing"] | frame["is_in_zone"])).any():
        raise ValueError("Feature invariant failed: every chase must be an out-of-zone swing.")


def build_dataset(
    savant_csv: Path,
    video_table: Path,
    output: Path,
    video_sheet: str = "Video Links",
    require_all_video: bool = False,
) -> pd.DataFrame:
    """Run extraction, transformation, join, validation, and load."""
    pitches = load_savant(savant_csv)
    expected_rows = len(pitches)
    pitches = standardize_and_derive(pitches)
    video = load_video_table(video_table, video_sheet)
    cleaned = join_video(pitches, video, require_all_video)
    cleaned = cleaned.reindex(columns=OUTPUT_COLUMNS)
    validate_output(cleaned, expected_rows)

    output.parent.mkdir(parents=True, exist_ok=True)
    cleaned.to_csv(output, index=False, encoding="utf-8-sig", na_rep="")
    return cleaned


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Create an analysis-ready Savant dataset joined to pitch videos."
    )
    parser.add_argument("--savant-csv", required=True, type=Path)
    parser.add_argument("--video-table", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument(
        "--video-sheet",
        default="Video Links",
        help="Excel sheet containing the video table (default: Video Links).",
    )
    parser.add_argument(
        "--require-all-video",
        action="store_true",
        help="Stop the run if any pitch lacks a video URL.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    cleaned = build_dataset(
        savant_csv=args.savant_csv,
        video_table=args.video_table,
        output=args.output,
        video_sheet=args.video_sheet,
        require_all_video=args.require_all_video,
    )

    print(f"Wrote cleaned dataset: {args.output.resolve()}")
    print(f"Rows: {len(cleaned):,}")
    print(f"Unique pitch_id values: {cleaned['pitch_id'].nunique():,}")
    print(
        "Video coverage: "
        f"{int(cleaned['has_video'].sum()):,}/{len(cleaned):,} "
        f"({cleaned['has_video'].mean():.1%})"
    )
    pitch_mix = cleaned["pitch_name"].value_counts().to_dict()
    print(f"Pitch mix: {pitch_mix}")


if __name__ == "__main__":
    main()
