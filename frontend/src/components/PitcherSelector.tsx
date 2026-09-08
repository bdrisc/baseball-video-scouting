import type { ChangeEvent } from "react";

import type { Pitcher } from "../types/api";

interface PitcherSelectorProps {
  pitchers: Pitcher[];
  selectedPitcherId: number | null;
  loading: boolean;
  onChange: (pitcherId: number | null) => void;
}

export default function PitcherSelector({
  pitchers,
  selectedPitcherId,
  loading,
  onChange,
}: PitcherSelectorProps) {
  function handleChange(event: ChangeEvent<HTMLSelectElement>) {
    const value = event.target.value;
    onChange(value ? Number(value) : null);
  }

  return (
    <label className="selector-field">
      <span>Pitcher</span>
      <select
        value={selectedPitcherId ?? ""}
        onChange={handleChange}
        disabled={loading}
      >
        <option value="">
          {loading ? "Loading pitchers..." : "Select a pitcher"}
        </option>
        {pitchers.map((pitcher) => (
          <option key={pitcher.player_id} value={pitcher.player_id}>
            {pitcher.player_name} · {pitcher.throws ?? "?"}HP ·{" "}
            {pitcher.pitch_count} pitches
          </option>
        ))}
      </select>
    </label>
  );
}
