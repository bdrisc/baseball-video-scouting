import { useMemo, useState } from "react";

import type { Pitch } from "../types/api";

interface PitchTableProps {
  pitches: Pitch[];
  totalMatches: number;
  loading: boolean;
  selectedPitchId: string | null;
  stagedPitchIds: string[];
  onSelect: (pitch: Pitch) => void;
  onAddToPlaylist: (pitch: Pitch) => void;
}

function readableResult(value: string | null): string {
  if (!value) return "—";
  return value.replaceAll("_", " ");
}

export default function PitchTable({
  pitches,
  totalMatches,
  loading,
  selectedPitchId,
  stagedPitchIds,
  onSelect,
  onAddToPlaylist,
}: PitchTableProps) {
  const [searchTerm, setSearchTerm] = useState("");

  const visiblePitches = useMemo(() => {
    const query = searchTerm.trim().toLowerCase();
    if (!query) return pitches;

    return pitches.filter((pitch) =>
      [
        pitch.pitch_id,
        pitch.pitch_type,
        pitch.batter_name,
        pitch.description,
        pitch.events,
        pitch.game_date,
      ]
        .filter(Boolean)
        .some((value) => String(value).toLowerCase().includes(query)),
    );
  }, [pitches, searchTerm]);

  return (
    <section className="panel results-panel">
      <div className="panel-heading">
        <div>
          <p className="eyebrow">Search results</p>
          <h2>Pitch table</h2>
        </div>
        <span className="result-count">
          {loading ? "Searching…" : `${totalMatches} matches`}
        </span>
      </div>

      <div className="table-toolbar">
        <label>
          <span className="sr-only">Search loaded pitch rows</span>
          <input
            className="table-search"
            type="search"
            value={searchTerm}
            placeholder="Search pitch ID, type, batter, or result"
            onChange={(event) => setSearchTerm(event.target.value)}
          />
        </label>
        <span>
          {visiblePitches.length} visible · {pitches.length} loaded
        </span>
      </div>

      {loading && pitches.length === 0 ? (
        <div className="empty-state">
          <strong>Searching PostgreSQL…</strong>
          <span>React is requesting matching pitches from FastAPI.</span>
        </div>
      ) : visiblePitches.length === 0 ? (
        <div className="empty-state">
          <strong>No pitches match the current search.</strong>
          <span>Adjust the filters or clear the table search.</span>
        </div>
      ) : (
        <div className="table-scroll">
          <table>
            <thead>
              <tr>
                <th>Date</th>
                <th>Batter</th>
                <th>Pitch</th>
                <th>Velocity</th>
                <th>Count</th>
                <th>Result</th>
                <th>Location</th>
                <th>Video</th>
                <th>Playlist</th>
              </tr>
            </thead>
            <tbody>
              {visiblePitches.map((pitch) => {
                const staged = stagedPitchIds.includes(pitch.pitch_id);
                return (
                <tr
                  key={pitch.pitch_id}
                  id={`pitch-row-${pitch.pitch_id}`}
                  className={
                    pitch.pitch_id === selectedPitchId ? "selected-row" : ""
                  }
                  onClick={() => onSelect(pitch)}
                >
                  <td>{pitch.game_date}</td>
                  <td>{pitch.batter_name ?? "—"}</td>
                  <td>{pitch.pitch_type}</td>
                  <td className="numeric-cell">
                    {pitch.velocity?.toFixed(1) ?? "—"}
                  </td>
                  <td>
                    {pitch.balls}-{pitch.strikes}
                  </td>
                  <td>{readableResult(pitch.description ?? pitch.events)}</td>
                  <td className="numeric-cell">
                    {pitch.plate_x?.toFixed(2) ?? "—"},{" "}
                    {pitch.plate_z?.toFixed(2) ?? "—"}
                  </td>
                  <td>
                    <span
                      className={`video-badge ${
                        pitch.video_available ? "available" : "unavailable"
                      }`}
                    >
                      {pitch.video_available ? "Video" : "None"}
                    </span>
                  </td>
                  <td>
                    <button
                      className="table-action"
                      type="button"
                      disabled={staged}
                      onClick={(event) => {
                        event.stopPropagation();
                        onAddToPlaylist(pitch);
                      }}
                    >
                      {staged ? "Added" : "+ Add"}
                    </button>
                  </td>
                </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}
