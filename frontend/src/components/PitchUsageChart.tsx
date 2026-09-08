import { useMemo } from "react";
import Plot from "react-plotly.js";
import type { Data, Layout } from "plotly.js";

import type { Pitch } from "../types/api";
import {
  baseLayout,
  groupByPitchType,
  pitchColor,
  pitchLabel,
  plotConfig,
} from "./chartHelpers";

interface PitchUsageChartProps {
  pitches: Pitch[];
}

export default function PitchUsageChart({ pitches }: PitchUsageChartProps) {
  const data = useMemo<Data[]>(() => {
    const groups = [...groupByPitchType(pitches)];
    return [
      {
        type: "bar",
        x: groups.map(([pitchType]) => pitchType),
        y: groups.map(([, group]) => (group.length / pitches.length) * 100),
        customdata: groups.map(([, group]) => group.length),
        text: groups.map(
          ([, group]) => `${((group.length / pitches.length) * 100).toFixed(1)}%`,
        ),
        textposition: "outside",
        cliponaxis: false,
        marker: {
          color: groups.map(([pitchType]) => pitchColor(pitchType)),
        },
        hovertemplate:
          "%{x}: %{y:.1f}%<br>%{customdata} pitches<extra></extra>",
      },
    ];
  }, [pitches]);

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
        <span className="result-count">{pitches.length} pitches</span>
      </div>
      {pitches.length ? (
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
        {pitches.length
          ? [...groupByPitchType(pitches)]
              .map(([pitchType]) => `${pitchType} · ${pitchLabel(pitchType)}`)
              .join("  |  ")
          : "Usage reflects the currently loaded pitches."}
      </p>
    </section>
  );
}
