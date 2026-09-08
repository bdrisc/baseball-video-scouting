import { useEffect, useMemo, useState } from "react";

import type { Pitch } from "../types/api";

interface VideoPanelProps {
  pitch: Pitch | null;
  pitches: Pitch[];
  stagedPitchIds: string[];
  onSelect: (pitch: Pitch) => void;
  onAddToPlaylist: (pitch: Pitch) => void;
  playlistReviewActive: boolean;
  onExitPlaylistReview: () => void;
}

function hasVideo(pitch: Pitch): boolean {
  return Boolean(pitch.video_available && pitch.video_url);
}

function isOfficialDirectMlbVideo(url: string | null): boolean {
  if (!url) return false;

  try {
    const parsedUrl = new URL(url);
    const officialHost =
      parsedUrl.hostname === "sporty-clips.mlb.com" ||
      parsedUrl.hostname.endsWith(".mlb.com");
    return (
      parsedUrl.protocol === "https:" &&
      officialHost &&
      parsedUrl.pathname.toLowerCase().endsWith(".mp4")
    );
  } catch {
    return false;
  }
}

function pitchSummary(pitch: Pitch): string {
  return `${pitch.pitch_type} · ${pitch.velocity?.toFixed(1) ?? "—"} mph · ${pitch.balls}-${pitch.strikes}`;
}

export default function VideoPanel({
  pitch,
  pitches,
  stagedPitchIds,
  onSelect,
  onAddToPlaylist,
  playlistReviewActive,
  onExitPlaylistReview,
}: VideoPanelProps) {
  const [embedFailed, setEmbedFailed] = useState(false);
  const videoAvailable = Boolean(pitch?.video_available && pitch.video_url);
  const directVideo = isOfficialDirectMlbVideo(pitch?.video_url ?? null);
  const staged = pitch ? stagedPitchIds.includes(pitch.pitch_id) : false;

  useEffect(() => {
    setEmbedFailed(false);
  }, [pitch?.video_url]);

  const navigation = useMemo(() => {
    if (!pitch) {
      return {
        previous: null,
        next: null,
        videoPosition: null,
        videoCount: pitches.filter(hasVideo).length,
      };
    }

    const selectedIndex = pitches.findIndex(
      (item) => item.pitch_id === pitch.pitch_id,
    );
    const videoPitches = pitches.filter(hasVideo);
    const videoPosition = videoPitches.findIndex(
      (item) => item.pitch_id === pitch.pitch_id,
    );

    if (videoPosition >= 0) {
      return {
        previous: videoPitches[videoPosition - 1] ?? null,
        next: videoPitches[videoPosition + 1] ?? null,
        videoPosition: videoPosition + 1,
        videoCount: videoPitches.length,
      };
    }

    const before = pitches.slice(0, Math.max(selectedIndex, 0)).filter(hasVideo);
    const after = pitches.slice(selectedIndex + 1).filter(hasVideo);
    return {
      previous: before.at(-1) ?? null,
      next: after[0] ?? null,
      videoPosition: null,
      videoCount: videoPitches.length,
    };
  }, [pitch, pitches]);

  return (
    <section className="panel video-panel">
      <div className="panel-heading">
        <div>
          <p className="eyebrow">Official video</p>
          <h2>Video panel</h2>
        </div>
        <span className="result-count">
          {navigation.videoPosition
            ? `${navigation.videoPosition} of ${navigation.videoCount}`
            : `${navigation.videoCount} linked`}
        </span>
      </div>

      {playlistReviewActive ? (
        <div className="playlist-review-banner">
          <div>
            <strong>Playlist review active</strong>
            <span>Previous and next now follow the saved playlist order.</span>
          </div>
          <button type="button" onClick={onExitPlaylistReview}>
            Exit
          </button>
        </div>
      ) : null}

      {videoAvailable && directVideo && !embedFailed ? (
        <div className="video-player-wrap">
          <video
            key={pitch?.video_url}
            className="video-player"
            controls
            playsInline
            preload="metadata"
            onError={() => setEmbedFailed(true)}
          >
            <source src={pitch?.video_url ?? undefined} type="video/mp4" />
            Your browser does not support HTML5 video.
          </video>
        </div>
      ) : (
        <div className="video-stage">
          <span className="play-mark">▶</span>
          <strong>
            {videoAvailable
              ? embedFailed
                ? "Use the official MLB viewer"
                : "Official MLB video available"
              : pitch
                ? "No video linked to this pitch"
                : "Select a pitch to review video"}
          </strong>
          <span>
            {pitch
              ? pitchSummary(pitch)
              : "Choose a row or a point on an interactive chart."}
          </span>
        </div>
      )}

      {videoAvailable ? (
        <a
          className="primary-button"
          href={pitch?.video_url ?? undefined}
          target="_blank"
          rel="noreferrer"
        >
          Watch in MLB Film Room ↗
        </a>
      ) : (
        <button className="primary-button" type="button" disabled>
          Video unavailable
        </button>
      )}

      <div className="video-navigation" aria-label="Video navigation">
        <button
          className="secondary-button video-nav-button"
          type="button"
          disabled={!navigation.previous}
          onClick={() => {
            if (navigation.previous) onSelect(navigation.previous);
          }}
        >
          ← Previous video
        </button>
        <button
          className="secondary-button video-nav-button"
          type="button"
          disabled={!navigation.next}
          onClick={() => {
            if (navigation.next) onSelect(navigation.next);
          }}
        >
          Next video →
        </button>
      </div>

      <button
        className="secondary-button video-playlist-button"
        type="button"
        disabled={!pitch || staged}
        onClick={() => {
          if (pitch) onAddToPlaylist(pitch);
        }}
      >
        {staged ? "Added to staged playlist" : "+ Add to playlist"}
      </button>

      <p className="video-source-note">
        Navigation follows the {playlistReviewActive ? "playlist" : "currently filtered pitch results"}.
        Video remains hosted by MLB and is not downloaded or stored by this application.
      </p>
    </section>
  );
}
