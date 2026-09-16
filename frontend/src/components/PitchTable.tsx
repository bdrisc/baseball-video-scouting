import { useMemo, useState } from "react";

import type {
  Pitch,
  PitchSortField,
  SortOrder,
} from "../types/api";

interface PitchTableProps {
  pitches: Pitch[];
  totalMatches: number;
  limit: number;
  offset: number;
  sortBy: PitchSortField;
  sortOrder: SortOrder;
  loading: boolean;
  selectedPitchId: string | null;
  stagedPitchIds: string[];
  onSelect: (pitch: Pitch) => void;
  onAddToPlaylist: (pitch: Pitch) => void;
  onPageChange: (offset: number) => void;
  onPageSizeChange: (limit: number) => void;
  onSortChange: (field: PitchSortField, order: SortOrder) => void;
}

function readableResult(value: string | null): string {
  if (!value) return "—";
  return value.replaceAll("_", " ");
}

export default function PitchTable({
  pitches,
  totalMatches,
  limit,
  offset,
  sortBy,
  sortOrder,
  loading,
  selectedPitchId,
  stagedPitchIds,
  onSelect,
  onAddToPlaylist,
  onPageChange,
  onPageSizeChange,
  onSortChange,
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

  const firstResult = totalMatches === 0 ? 0 : offset + 1;
  const lastResult = Math.min(offset + pitches.length, totalMatches);
  const currentPage = totalMatches === 0 ? 1 : Math.floor(offset / limit) + 1;
  const pageCount = Math.max(1, Math.ceil(totalMatches / limit));

  function sortHeader(label: string, field: PitchSortField) {
    const active = sortBy === field;
    const nextOrder: SortOrder = active && sortOrder === "asc" ? "desc" : "asc";

    return (
      <button
        className={`sort-button ${active ? "active" : ""}`}
        type="button"
        aria-label={`Sort by ${label} ${nextOrder === "asc" ? "ascending" : "descending"}`}
        onClick={() => onSortChange(field, nextOrder)}
      >
        {label}
        <span aria-hidden="true">{active ? (sortOrder === "asc" ? "↑" : "↓") : "↕"}</span>
      </button>
    );
  }

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
        <div className="table-toolbar-meta">
          <span>{visiblePitches.length} visible · {pitches.length} loaded</span>
          <label className="page-size-control">
            <span>Rows</span>
            <select
              value={limit}
              disabled={loading}
              onChange={(event) => onPageSizeChange(Number(event.target.value))}
            >
              <option value={100}>100</option>
              <option value={250}>250</option>
              <option value={500}>500</option>
            </select>
          </label>
        </div>
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
                <th>{sortHeader("Date", "game_date")}</th>
                <th>{sortHeader("Batter", "batter_name")}</th>
                <th>{sortHeader("Pitch", "pitch_type")}</th>
                <th>{sortHeader("Velocity", "velocity")}</th>
                <th>Count</th>
                <th>{sortHeader("Result", "result")}</th>
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

      <nav className="pagination-controls" aria-label="Pitch results pages">
        <span>
          Showing {firstResult.toLocaleString()}–{lastResult.toLocaleString()} of{" "}
          {totalMatches.toLocaleString()}
        </span>
        <div>
          <button
            className="secondary-button"
            type="button"
            disabled={loading || offset === 0}
            onClick={() => onPageChange(Math.max(0, offset - limit))}
          >
            Previous
          </button>
          <span>
            Page {currentPage.toLocaleString()} of {pageCount.toLocaleString()}
          </span>
          <button
            className="secondary-button"
            type="button"
            disabled={loading || offset + pitches.length >= totalMatches}
            onClick={() => onPageChange(offset + limit)}
          >
            Next
          </button>
        </div>
      </nav>
    </section>
  );
}
