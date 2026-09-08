import type { ChangeEvent } from "react";

import type { Game } from "../types/api";

interface GameSelectorProps {
  games: Game[];
  selectedGamePk: number | null;
  disabled: boolean;
  loading: boolean;
  onChange: (gamePk: number | null) => void;
}

function formatGame(game: Game): string {
  const date = new Date(`${game.game_date}T12:00:00`).toLocaleDateString(
    "en-US",
    { month: "short", day: "numeric", year: "numeric" },
  );
  return `${date} · ${game.away_team} at ${game.home_team}`;
}

export default function GameSelector({
  games,
  selectedGamePk,
  disabled,
  loading,
  onChange,
}: GameSelectorProps) {
  function handleChange(event: ChangeEvent<HTMLSelectElement>) {
    const value = event.target.value;
    onChange(value ? Number(value) : null);
  }

  return (
    <label className="selector-field">
      <span>Game</span>
      <select
        value={selectedGamePk ?? ""}
        onChange={handleChange}
        disabled={disabled || loading}
      >
        <option value="">
          {loading ? "Loading games..." : "All available games"}
        </option>
        {games.map((game) => (
          <option key={game.game_pk} value={game.game_pk}>
            {formatGame(game)} · {game.pitch_count} pitches
          </option>
        ))}
      </select>
    </label>
  );
}
