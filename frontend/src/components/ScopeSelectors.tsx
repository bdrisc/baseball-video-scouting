import type { SeasonSummary, TeamSummary } from "../types/api";

interface ScopeSelectorsProps {
  seasons: SeasonSummary[];
  teams: TeamSummary[];
  selectedSeason: number | null;
  selectedTeamId: number | null;
  loading: boolean;
  onSeasonChange: (season: number | null) => void;
  onTeamChange: (teamId: number | null) => void;
}

export default function ScopeSelectors({
  seasons,
  teams,
  selectedSeason,
  selectedTeamId,
  loading,
  onSeasonChange,
  onTeamChange,
}: ScopeSelectorsProps) {
  return (
    <>
      <label className="selector-field">
        <span>Season</span>
        <select
          value={selectedSeason ?? ""}
          disabled={loading}
          onChange={(event) =>
            onSeasonChange(event.target.value ? Number(event.target.value) : null)
          }
        >
          <option value="">All seasons</option>
          {seasons.map((season) => (
            <option key={season.season} value={season.season}>
              {season.season} · {season.pitch_count.toLocaleString()} pitches
            </option>
          ))}
        </select>
      </label>

      <label className="selector-field">
        <span>Team</span>
        <select
          value={selectedTeamId ?? ""}
          disabled={loading || !teams.length}
          onChange={(event) =>
            onTeamChange(event.target.value ? Number(event.target.value) : null)
          }
        >
          <option value="">All teams</option>
          {teams.map((team) => (
            <option key={team.team_id} value={team.team_id}>
              {team.team_name} · {team.pitcher_count} pitchers
            </option>
          ))}
        </select>
      </label>
    </>
  );
}
