import { useMemo } from "react";

import type { Pitch } from "../types/api";

interface SummaryStatsProps {
  pitches: Pitch[];
  totalMatches: number;
  loading: boolean;
}

const whiffDescriptions = new Set([
  "swinging_strike",
  "swinging_strike_blocked",
  "missed_bunt",
]);

export default function SummaryStats({
  pitches,
  totalMatches,
  loading,
}: SummaryStatsProps) {
  const stats = useMemo(() => {
    const velocities = pitches
      .map((pitch) => pitch.velocity)
      .filter((velocity): velocity is number => velocity !== null);
    const averageVelocity = velocities.length
      ? velocities.reduce((total, velocity) => total + velocity, 0) /
        velocities.length
      : null;
    const whiffs = pitches.filter((pitch) =>
      whiffDescriptions.has(pitch.description ?? ""),
    ).length;
    const videos = pitches.filter((pitch) => pitch.video_available).length;
    const pitchTypes = new Set(pitches.map((pitch) => pitch.pitch_type)).size;

    return { averageVelocity, whiffs, videos, pitchTypes };
  }, [pitches]);

  return (
    <section className="summary-grid" aria-label="Pitch search summary">
      <div className="stat-card featured-stat">
        <span>Matching pitches</span>
        <strong>{loading ? "…" : totalMatches}</strong>
      </div>
      <div className="stat-card">
        <span>Average velocity</span>
        <strong>
          {stats.averageVelocity === null
            ? "—"
            : `${stats.averageVelocity.toFixed(1)} mph`}
        </strong>
      </div>
      <div className="stat-card">
        <span>Whiffs</span>
        <strong>{stats.whiffs}</strong>
      </div>
      <div className="stat-card">
        <span>Videos available</span>
        <strong>{stats.videos}</strong>
      </div>
      <div className="stat-card">
        <span>Pitch types</span>
        <strong>{stats.pitchTypes}</strong>
      </div>
    </section>
  );
}
