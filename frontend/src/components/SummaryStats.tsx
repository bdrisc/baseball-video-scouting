import type { PitchAggregateSummary } from "../types/api";

interface SummaryStatsProps {
  summary: PitchAggregateSummary | null;
  loading: boolean;
}

export default function SummaryStats({
  summary,
  loading,
}: SummaryStatsProps) {
  return (
    <section className="summary-grid" aria-label="Pitch search summary">
      <div className="stat-card featured-stat">
        <span>Matching pitches</span>
        <strong>{loading ? "…" : (summary?.total_pitches ?? 0)}</strong>
      </div>
      <div className="stat-card">
        <span>Average velocity</span>
        <strong>
          {summary?.average_velocity === null || summary === null
            ? "—"
            : `${summary.average_velocity.toFixed(1)} mph`}
        </strong>
      </div>
      <div className="stat-card">
        <span>Whiffs</span>
        <strong>{loading ? "…" : (summary?.whiffs ?? 0)}</strong>
      </div>
      <div className="stat-card">
        <span>Videos available</span>
        <strong>{loading ? "…" : (summary?.videos_available ?? 0)}</strong>
      </div>
      <div className="stat-card">
        <span>Pitch types</span>
        <strong>{loading ? "…" : (summary?.pitch_types ?? 0)}</strong>
      </div>
    </section>
  );
}
