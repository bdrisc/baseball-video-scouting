import { useMemo } from "react";
import Plot from "react-plotly.js";
import type { Data, Layout } from "plotly.js";

import type { UsageByCountAggregate } from "../types/api";
import { baseLayout, plotConfig } from "./chartHelpers";

interface UsageByCountChartProps {
  rows: UsageByCountAggregate[];
}

const COUNT_ORDER = [
  "0-0",
  "1-0",
  "0-1",
  "2-0",
  "1-1",
  "0-2",
  "3-0",
  "2-1",
  "1-2",
  "3-1",
  "2-2",
  "3-2",
];

export default function UsageByCountChart({ rows }: UsageByCountChartProps) {
  const pitchTypes = useMemo(() => {
    const totals = new Map<string, number>();
    rows.forEach((row) =>
      totals.set(
        row.pitch_type,
        (totals.get(row.pitch_type) ?? 0) + row.pitch_count,
      ),
    );
    return [...totals.entries()]
      .sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0]))
      .map(([pitchType]) => pitchType);
  }, [rows]);

  const data = useMemo<Data[]>(() => {
    const counts = pitchTypes.map((pitchType) =>
      COUNT_ORDER.map((count) => {
        const row = rows.find(
          (candidate) =>
            candidate.pitch_type === pitchType &&
            `${candidate.balls}-${candidate.strikes}` === count,
        );
        return row?.pitch_count ?? 0;
      }),
    );
    const percentages = pitchTypes.map((pitchType) =>
      COUNT_ORDER.map((count) => {
        const row = rows.find(
          (candidate) =>
            candidate.pitch_type === pitchType &&
            `${candidate.balls}-${candidate.strikes}` === count,
        );
        return row?.usage_percent ?? 0;
      }),
    );

    return [
      {
        type: "heatmap",
        x: COUNT_ORDER,
        y: pitchTypes,
        z: percentages,
        customdata: counts,
        text: percentages.map((row) =>
          row.map((value) => (value ? `${value.toFixed(0)}%` : "")),
        ),
        texttemplate: "%{text}",
        hovertemplate:
          "%{y} in %{x} counts<br>%{z:.1f}% usage<br>%{customdata} pitches<extra></extra>",
        colorscale: [
          [0, "#f7f1f3"],
          [0.35, "#d5a6b0"],
          [0.7, "#a53950"],
          [1, "#5a0013"],
        ],
        zmin: 0,
        zmax: 100,
        colorbar: { title: { text: "%" }, thickness: 10, len: 0.8 },
      },
    ];
  }, [pitchTypes, rows]);

  const layout = useMemo<Partial<Layout>>(
    () => ({
      ...baseLayout,
      margin: { l: 46, r: 52, t: 12, b: 42 },
      xaxis: { title: { text: "Count" }, fixedrange: true },
      yaxis: { title: { text: "Pitch type" }, fixedrange: true },
    }),
    [],
  );

  return (
    <section className="panel chart-card">
      <div className="panel-heading">
        <div>
          <p className="eyebrow">Approach</p>
          <h2>Usage by count</h2>
        </div>
        <span className="result-count">Column %</span>
      </div>
      {rows.length && pitchTypes.length ? (
        <div className="plot-container summary-plot">
          <Plot
            data={data}
            layout={layout}
            config={plotConfig}
            useResizeHandler
            style={{ width: "100%", height: "100%" }}
          />
        </div>
      ) : (
        <div className="empty-state chart-empty">
          <strong>No count data</strong>
          <span>Select a pitcher or broaden the current filters.</span>
        </div>
      )}
      <p className="chart-caption">
        Each column shows pitch-type usage within that count across the complete
        filtered result.
      </p>
    </section>
  );
}
