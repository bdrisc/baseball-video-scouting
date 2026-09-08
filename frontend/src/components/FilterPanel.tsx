import type { ChangeEvent } from "react";

import type { PitchSearchFilters } from "../types/api";

type EditableFilters = Omit<
  PitchSearchFilters,
  "pitcher_id" | "game_pk" | "limit" | "offset"
>;

interface FilterPanelProps {
  filters: EditableFilters;
  disabled: boolean;
  onChange: (filters: EditableFilters) => void;
  onReset: () => void;
}

const pitchTypes = [
  ["FF", "Four-seam"],
  ["SI", "Sinker"],
  ["FC", "Cutter"],
  ["SL", "Slider"],
  ["ST", "Sweeper"],
  ["CU", "Curveball"],
  ["KC", "Knuckle curve"],
  ["CH", "Changeup"],
  ["FS", "Splitter"],
];

const results = [
  ["ball", "Ball"],
  ["called_strike", "Called strike"],
  ["swinging_strike", "Swinging strike"],
  ["swinging_strike_blocked", "Swinging strike (blocked)"],
  ["foul", "Foul"],
  ["foul_tip", "Foul tip"],
  ["hit_into_play", "In play"],
  ["blocked_ball", "Blocked ball"],
  ["hit_by_pitch", "Hit by pitch"],
];

const counts = Array.from({ length: 4 }, (_, balls) =>
  Array.from({ length: 3 }, (_unused, strikes) => `${balls}-${strikes}`),
).flat();

function nullableNumber(event: ChangeEvent<HTMLInputElement>): number | null {
  return event.target.value === "" ? null : Number(event.target.value);
}

export default function FilterPanel({
  filters,
  disabled,
  onChange,
  onReset,
}: FilterPanelProps) {
  const countValue =
    filters.balls === null || filters.strikes === null
      ? ""
      : `${filters.balls}-${filters.strikes}`;

  function handleCountChange(event: ChangeEvent<HTMLSelectElement>) {
    if (!event.target.value) {
      onChange({ ...filters, balls: null, strikes: null });
      return;
    }
    const [balls, strikes] = event.target.value.split("-").map(Number);
    onChange({ ...filters, balls, strikes });
  }

  return (
    <section className="panel filter-panel">
      <div className="panel-heading">
        <div>
          <p className="eyebrow">Search controls</p>
          <h2>Pitch filters</h2>
        </div>
        <button
          className="text-button"
          type="button"
          onClick={onReset}
          disabled={disabled}
        >
          Reset
        </button>
      </div>

      <div className="filter-controls">
        <label className="filter-field">
          <span>Batter side</span>
          <select
            value={filters.batter_side}
            disabled={disabled}
            onChange={(event) =>
              onChange({
                ...filters,
                batter_side: event.target.value as "" | "L" | "R",
              })
            }
          >
            <option value="">Both sides</option>
            <option value="L">Left-handed</option>
            <option value="R">Right-handed</option>
          </select>
        </label>

        <label className="filter-field">
          <span>Pitch type</span>
          <select
            value={filters.pitch_type}
            disabled={disabled}
            onChange={(event) =>
              onChange({ ...filters, pitch_type: event.target.value })
            }
          >
            <option value="">All pitch types</option>
            {pitchTypes.map(([code, label]) => (
              <option key={code} value={code}>
                {label} ({code})
              </option>
            ))}
          </select>
        </label>

        <label className="filter-field">
          <span>Count</span>
          <select
            value={countValue}
            disabled={disabled}
            onChange={handleCountChange}
          >
            <option value="">All counts</option>
            {counts.map((count) => (
              <option key={count} value={count}>
                {count}
              </option>
            ))}
          </select>
        </label>

        <label className="filter-field">
          <span>Pitch result</span>
          <select
            value={filters.result}
            disabled={disabled}
            onChange={(event) =>
              onChange({ ...filters, result: event.target.value })
            }
          >
            <option value="">All results</option>
            {results.map(([value, label]) => (
              <option key={value} value={value}>
                {label}
              </option>
            ))}
          </select>
        </label>

        <fieldset className="range-field" disabled={disabled}>
          <legend>Velocity (mph)</legend>
          <div className="range-row">
            <input
              type="number"
              min="0"
              max="110"
              step="0.1"
              placeholder="Min"
              aria-label="Minimum velocity"
              value={filters.min_velocity ?? ""}
              onChange={(event) =>
                onChange({ ...filters, min_velocity: nullableNumber(event) })
              }
            />
            <span>to</span>
            <input
              type="number"
              min="0"
              max="110"
              step="0.1"
              placeholder="Max"
              aria-label="Maximum velocity"
              value={filters.max_velocity ?? ""}
              onChange={(event) =>
                onChange({ ...filters, max_velocity: nullableNumber(event) })
              }
            />
          </div>
        </fieldset>

        <fieldset className="range-field" disabled={disabled}>
          <legend>Horizontal location (ft)</legend>
          <div className="range-row">
            <input
              type="number"
              min="-5"
              max="5"
              step="0.1"
              placeholder="Min"
              aria-label="Minimum horizontal location"
              value={filters.min_plate_x ?? ""}
              onChange={(event) =>
                onChange({ ...filters, min_plate_x: nullableNumber(event) })
              }
            />
            <span>to</span>
            <input
              type="number"
              min="-5"
              max="5"
              step="0.1"
              placeholder="Max"
              aria-label="Maximum horizontal location"
              value={filters.max_plate_x ?? ""}
              onChange={(event) =>
                onChange({ ...filters, max_plate_x: nullableNumber(event) })
              }
            />
          </div>
        </fieldset>

        <fieldset className="range-field" disabled={disabled}>
          <legend>Vertical location (ft)</legend>
          <div className="range-row">
            <input
              type="number"
              min="-2"
              max="8"
              step="0.1"
              placeholder="Min"
              aria-label="Minimum vertical location"
              value={filters.min_plate_z ?? ""}
              onChange={(event) =>
                onChange({ ...filters, min_plate_z: nullableNumber(event) })
              }
            />
            <span>to</span>
            <input
              type="number"
              min="-2"
              max="8"
              step="0.1"
              placeholder="Max"
              aria-label="Maximum vertical location"
              value={filters.max_plate_z ?? ""}
              onChange={(event) =>
                onChange({ ...filters, max_plate_z: nullableNumber(event) })
              }
            />
          </div>
        </fieldset>

        <label className="filter-field">
          <span>Video availability</span>
          <select
            value={
              filters.video_available === null
                ? ""
                : String(filters.video_available)
            }
            disabled={disabled}
            onChange={(event) =>
              onChange({
                ...filters,
                video_available:
                  event.target.value === ""
                    ? null
                    : event.target.value === "true",
              })
            }
          >
            <option value="">All pitches</option>
            <option value="true">Video available</option>
            <option value="false">No video</option>
          </select>
        </label>
      </div>
    </section>
  );
}
