import { useEffect, useState } from "react";

import {
  createPlaylist,
  getPlaylist,
  getPlaylists,
  savePlaylistItems,
  updatePlaylist,
} from "../services/api";
import type { Pitch, PlaylistDetail, PlaylistSummary } from "../types/api";

interface PlaylistBuilderProps {
  stagedPitches: Pitch[];
  scoutingNotes: Record<string, string>;
  onScoutingNoteChange: (pitchId: string, note: string) => void;
  onSelectPitch: (pitch: Pitch) => void;
  onMove: (pitchId: string, direction: "up" | "down") => void;
  onRemove: (pitchId: string) => void;
  onClear: () => void;
  initialPlaylistId: number | null;
  onLoadPlaylist: (playlist: PlaylistDetail | null) => void;
  onStartReview: () => void;
  readOnly: boolean;
}

const EXAMPLE_PLAYLISTS = [
  "Two-strike breaking balls",
  "Fastballs above the zone",
  "Changeups against left-handed hitters",
  "Hard contact allowed",
  "Best finish pitches",
];

export default function PlaylistBuilder({
  readOnly,
  stagedPitches,
  scoutingNotes,
  onScoutingNoteChange,
  onSelectPitch,
  onMove,
  onRemove,
  onClear,
  initialPlaylistId,
  onLoadPlaylist,
  onStartReview,
}: PlaylistBuilderProps) {
  const [savedPlaylists, setSavedPlaylists] = useState<PlaylistSummary[]>([]);
  const [activePlaylistId, setActivePlaylistId] = useState<number | null>(null);
  const [playlistName, setPlaylistName] = useState("");
  const [description, setDescription] = useState("");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [statusMessage, setStatusMessage] = useState<string | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  async function refreshSavedPlaylists(signal?: AbortSignal) {
    const playlists = await getPlaylists(signal);
    setSavedPlaylists(playlists);
  }

  useEffect(() => {
    const controller = new AbortController();

    async function loadPlaylistList() {
      setLoading(true);
      setErrorMessage(null);
      try {
        await refreshSavedPlaylists(controller.signal);
        if (initialPlaylistId !== null) {
          await loadPlaylist(initialPlaylistId);
        }
      } catch (error) {
        if (!controller.signal.aborted) {
          setErrorMessage(
            error instanceof Error ? error.message : "Could not load playlists.",
          );
        }
      } finally {
        if (!controller.signal.aborted) setLoading(false);
      }
    }

    void loadPlaylistList();
    return () => controller.abort();
  }, [initialPlaylistId]);

  async function loadPlaylist(playlistId: number) {
    setLoading(true);
    setStatusMessage(null);
    setErrorMessage(null);

    try {
      const playlist = await getPlaylist(playlistId);
      setActivePlaylistId(playlist.playlist_id);
      setPlaylistName(playlist.playlist_name);
      setDescription(playlist.description ?? "");
      onLoadPlaylist(playlist);
      setStatusMessage(`Loaded ${playlist.items.length} saved pitches.`);
    } catch (error) {
      setErrorMessage(
        error instanceof Error ? error.message : "Could not load the playlist.",
      );
    } finally {
      setLoading(false);
    }
  }

  async function savePlaylist() {
    if (readOnly) {
      setErrorMessage(
        "Playlist saving is disabled in the public portfolio demo.",
      );
      return;
    }
    const normalizedName = playlistName.trim();
    if (!normalizedName) {
      setErrorMessage("Enter a playlist name before saving.");
      return;
    }

    setSaving(true);
    setStatusMessage(null);
    setErrorMessage(null);

    try {
      const metadata = {
        playlist_name: normalizedName,
        description: description.trim() || null,
      };
      const savedMetadata =
        activePlaylistId === null
          ? await createPlaylist(metadata)
          : await updatePlaylist(activePlaylistId, metadata);

      const savedPlaylist = await savePlaylistItems(savedMetadata.playlist_id, {
        items: stagedPitches.map((pitch) => ({
          pitch_id: pitch.pitch_id,
          scouting_note: scoutingNotes[pitch.pitch_id]?.trim() || null,
        })),
      });

      setActivePlaylistId(savedPlaylist.playlist_id);
      setPlaylistName(savedPlaylist.playlist_name);
      setDescription(savedPlaylist.description ?? "");
      onLoadPlaylist(savedPlaylist);
      await refreshSavedPlaylists();
      setStatusMessage(
        `Saved “${savedPlaylist.playlist_name}” with ${savedPlaylist.items.length} pitches.`,
      );
    } catch (error) {
      setErrorMessage(
        error instanceof Error ? error.message : "Could not save the playlist.",
      );
    } finally {
      setSaving(false);
    }
  }

  function beginNewPlaylist() {
    setActivePlaylistId(null);
    setPlaylistName("");
    setDescription("");
    onLoadPlaylist(null);
    setStatusMessage("New playlist started. Your staged pitches were kept.");
    setErrorMessage(null);
  }

  const videoCount = stagedPitches.filter(
    (pitch) => pitch.video_available && pitch.video_url,
  ).length;

  return (
    <section className="panel playlist-panel">
      <div className="panel-heading">
        <div>
          <p className="eyebrow">Saved workflow</p>
          <h2>Playlist builder</h2>
        </div>
        <span className="result-count">
          {activePlaylistId ? `Playlist ${activePlaylistId}` : "New playlist"}
        </span>
      </div>

      {readOnly ? (
        <p className="playlist-status" role="status">
          Public demo mode: build and review playlists in this browser.
          Database saving is disabled.
        </p>
      ) : null}

      <div className="playlist-form">
        <label className="playlist-field">
          <span>Open saved playlist</span>
          <select
            value={activePlaylistId ?? ""}
            disabled={loading || saving}
            onChange={(event) => {
              const playlistId = Number(event.target.value);
              if (playlistId) void loadPlaylist(playlistId);
              else beginNewPlaylist();
            }}
          >
            <option value="">Create a new playlist</option>
            {savedPlaylists.map((playlist) => (
              <option key={playlist.playlist_id} value={playlist.playlist_id}>
                {playlist.playlist_name} ({playlist.item_count})
              </option>
            ))}
          </select>
        </label>

        <label className="playlist-field">
          <span>Playlist name</span>
          <input
            type="text"
            value={playlistName}
            maxLength={100}
            list="playlist-name-examples"
            placeholder="e.g. Two-strike breaking balls"
            disabled={saving}
            onChange={(event) => setPlaylistName(event.target.value)}
          />
          <datalist id="playlist-name-examples">
            {EXAMPLE_PLAYLISTS.map((example) => (
              <option key={example} value={example} />
            ))}
          </datalist>
        </label>

        <label className="playlist-field">
          <span>Description</span>
          <textarea
            value={description}
            maxLength={1000}
            rows={2}
            placeholder="Purpose, opponent, or scouting focus…"
            disabled={saving}
            onChange={(event) => setDescription(event.target.value)}
          />
        </label>
      </div>

      <div className="queue-summary playlist-queue-heading">
        <strong>
          {stagedPitches.length} pitches · {videoCount} videos
        </strong>
        <button
          className="text-button"
          type="button"
          disabled={!stagedPitches.length || saving}
          onClick={onClear}
        >
          Clear pitches
        </button>
      </div>

      {stagedPitches.length === 0 ? (
        <div className="empty-state compact">
          <strong>No pitches staged</strong>
          <span>
            {readOnly
              ? "Use Add in the table or video panel to build a review queue."
              : "Use Add in the table or video panel, then save the playlist."}
          </span>
        </div>
      ) : (
        <div className="playlist-queue editable-queue">
          <ol>
            {stagedPitches.map((pitch, index) => (
              <li key={pitch.pitch_id} className="playlist-editor-item">
                <div className="queue-item-topline">
                  <button
                    className="queue-pitch-button"
                    type="button"
                    onClick={() => onSelectPitch(pitch)}
                  >
                    <strong>
                      {index + 1}. {pitch.pitch_type} · {pitch.velocity?.toFixed(1) ?? "—"} mph
                    </strong>
                    <span>
                      {pitch.batter_name ?? "Unknown batter"} · {pitch.balls}-{pitch.strikes}
                    </span>
                  </button>
                  <div className="queue-order-buttons">
                    <button
                      type="button"
                      disabled={index === 0 || saving}
                      aria-label={`Move ${pitch.pitch_id} up`}
                      title="Move up"
                      onClick={() => onMove(pitch.pitch_id, "up")}
                    >
                      ↑
                    </button>
                    <button
                      type="button"
                      disabled={index === stagedPitches.length - 1 || saving}
                      aria-label={`Move ${pitch.pitch_id} down`}
                      title="Move down"
                      onClick={() => onMove(pitch.pitch_id, "down")}
                    >
                      ↓
                    </button>
                    <button
                      type="button"
                      disabled={saving}
                      aria-label={`Remove ${pitch.pitch_id} from playlist`}
                      title="Remove pitch"
                      onClick={() => onRemove(pitch.pitch_id)}
                    >
                      ×
                    </button>
                  </div>
                </div>
                <label className="queue-note-field">
                  <span className="sr-only">Scouting note for {pitch.pitch_id}</span>
                  <textarea
                    value={scoutingNotes[pitch.pitch_id] ?? ""}
                    maxLength={2000}
                    rows={2}
                    placeholder="Add a note for this pitch…"
                    disabled={saving}
                    onChange={(event) =>
                      onScoutingNoteChange(pitch.pitch_id, event.target.value)
                    }
                  />
                </label>
              </li>
            ))}
          </ol>
        </div>
      )}

      {errorMessage ? (
        <p className="playlist-status error" role="alert">
          {errorMessage}
        </p>
      ) : null}
      {statusMessage ? (
        <p className="playlist-status success" role="status">
          {statusMessage}
        </p>
      ) : null}

      <div className="playlist-actions">
        <button
          className="primary-button"
          type="button"
          disabled={readOnly || saving || loading}
          onClick={() => void savePlaylist()}
        >
          {readOnly
            ? "Saving disabled in public demo"
            : saving
              ? "Saving to PostgreSQL…"
              : activePlaylistId
                ? "Save changes"
                : "Create playlist"}
        </button>
        <button
          className="secondary-button"
          type="button"
          disabled={!videoCount || saving}
          onClick={onStartReview}
        >
          Review playlist videos
        </button>
        <button
          className="text-button new-playlist-button"
          type="button"
          disabled={saving}
          onClick={beginNewPlaylist}
        >
          Start a new playlist
        </button>
      </div>
    </section>
  );
}
