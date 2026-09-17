import type { Pitcher } from "../types/api";

interface PitcherSelectorProps {
  pitchers: Pitcher[];
  selectedPitcher: Pitcher | null;
  query: string;
  total: number;
  loading: boolean;
  onQueryChange: (query: string) => void;
  onChange: (pitcher: Pitcher | null) => void;
}

export default function PitcherSelector({
  pitchers,
  selectedPitcher,
  query,
  total,
  loading,
  onQueryChange,
  onChange,
}: PitcherSelectorProps) {
  const options =
    selectedPitcher &&
    !pitchers.some((pitcher) => pitcher.player_id === selectedPitcher.player_id)
      ? [selectedPitcher, ...pitchers]
      : pitchers;

  return (
    <div className="selector-field pitcher-selector-field">
      <label htmlFor="pitcher-search">Pitcher search</label>
      <input
        id="pitcher-search"
        type="search"
        value={query}
        placeholder="Search by pitcher name"
        disabled={loading}
        onChange={(event) => onQueryChange(event.target.value)}
      />
      <select
        aria-label="Pitcher results"
        value={selectedPitcher?.player_id ?? ""}
        onChange={(event) => {
          const playerId = Number(event.target.value);
          onChange(
            event.target.value
              ? options.find((pitcher) => pitcher.player_id === playerId) ?? null
              : null,
          );
        }}
        disabled={loading}
      >
        <option value="">
          {loading ? "Loading pitchers..." : "Select a pitcher"}
        </option>
        {options.map((pitcher) => (
          <option key={pitcher.player_id} value={pitcher.player_id}>
            {pitcher.player_name} · {pitcher.throws ?? "?"}HP ·{" "}
            {pitcher.pitch_count.toLocaleString()} pitches
          </option>
        ))}
      </select>
      <span className="selector-help">
        {loading
          ? "Searching…"
          : total > pitchers.length
            ? `Showing ${pitchers.length} of ${total}. Refine the name search.`
            : `${total} matching pitcher${total === 1 ? "" : "s"}`}
      </span>
    </div>
  );
}
