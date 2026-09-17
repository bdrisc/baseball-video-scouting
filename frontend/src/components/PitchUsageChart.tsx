import { useMemo } from "react";
import Plot from "react-plotly.js";
import type { Data, Layout } from "plotly.js";

import type { PitchUsageAggregate } from "../types/api";
import {
  baseLayout,
  pitchColor,
  pitchLabel,
  plotConfig,
} from "./chartHelpers";

interface PitchUsageChartProps {
  rows: PitchUsageAggregate[];
}

export default function PitchUsageChart({ rows }: PitchUsageChartProps) {
  const data = useMemo<Data[]>(() => {
    return [
      {
        type: "bar",
        x: rows.map((row) => row.pitch_type),
        y: rows.map((row) => row.usage_percent),
        customdata: rows.map((row) => row.pitch_count),
        text: rows.map((row) => `${row.usage_percent.toFixed(1)}%`),
        textposition: "outside",
        cliponaxis: false,
        marker: {
          color: rows.map((row) => pitchColor(row.pitch_type)),
        },
        hovertemplate:
          "%{x}: %{y:.1f}%<br>%{customdata} pitches<extra></extra>",
      },
    ];
  }, [rows]);

  const layout = useMemo<Partial<Layout>>(
    () => ({
      ...baseLayout,
      margin: { l: 50, r: 16, t: 22, b: 42 },
      showlegend: false,
      xaxis: { title: { text: "Pitch type" }, fixedrange: true },
      yaxis: {
        title: { text: "Usage %" },
        rangemode: "tozero",
        fixedrange: true,
        gridcolor: "#e7eaed",
      },
    }),
    [],
  );

  return (
    <section className="panel chart-card">
      <div className="panel-heading">
        <div>
          <p className="eyebrow">Arsenal</p>
          <h2>Pitch usage</h2>
        </div>
        <span className="result-count">
          {rows.reduce((total, row) => total + row.pitch_count, 0)} pitches
        </span>
      </div>
      {rows.length ? (
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
          <strong>No usage data</strong>
          <span>Select a pitcher or broaden the current filters.</span>
        </div>
      )}
      <p className="chart-caption">
        {rows.length
          ? rows
              .map(
                (row) =>
                  `${row.pitch_type} · ${pitchLabel(row.pitch_type)}`,
              )
              .join("  |  ")
          : "Usage reflects the complete filtered result."}
      </p>
    </section>
  );
}
