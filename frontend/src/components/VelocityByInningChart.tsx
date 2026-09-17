import { useMemo } from "react";
import Plot from "react-plotly.js";
import type { Data, Layout } from "plotly.js";

import type { VelocityByInningAggregate } from "../types/api";
import {
  baseLayout,
  pitchColor,
  plotConfig,
} from "./chartHelpers";

interface VelocityByInningChartProps {
  rows: VelocityByInningAggregate[];
}

export default function VelocityByInningChart({ rows }: VelocityByInningChartProps) {
  const data = useMemo<Data[]>(
    () => {
      const pitchTypes = [...new Set(rows.map((row) => row.pitch_type))];
      return pitchTypes.map((pitchType) => {
        const points = rows.filter((row) => row.pitch_type === pitchType);
        return {
          type: "scatter",
          mode: "lines+markers",
          name: pitchType,
          x: points.map((row) => row.inning),
          y: points.map((row) => row.average_velocity),
          customdata: points.map((row) => row.pitch_count),
          line: { color: pitchColor(pitchType), width: 2 },
          marker: { color: pitchColor(pitchType), size: 7 },
          hovertemplate:
            `${pitchType}<br>Inning %{x}<br>Average: %{y:.1f} mph<br>` +
            "%{customdata} pitches<extra></extra>",
        };
      });
    },
    [rows],
  );

  const layout = useMemo<Partial<Layout>>(
    () => ({
      ...baseLayout,
      margin: { l: 55, r: 16, t: 16, b: 45 },
      legend: { orientation: "h", x: 0, y: 1.12, font: { size: 10 } },
      xaxis: {
        title: { text: "Inning" },
        dtick: 1,
        fixedrange: true,
        gridcolor: "#edf0f2",
      },
      yaxis: {
        title: { text: "Average velocity (mph)" },
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
          <p className="eyebrow">Game progression</p>
          <h2>Velocity by inning</h2>
        </div>
        <span className="result-count">Average</span>
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
          <strong>No inning velocity data</strong>
          <span>The current pitches do not include both fields.</span>
        </div>
      )}
      <p className="chart-caption">
        Each point uses the complete filtered result for that pitch type and
        inning.
      </p>
    </section>
  );
}
