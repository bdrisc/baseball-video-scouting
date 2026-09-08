import { useMemo } from "react";
import Plot from "react-plotly.js";
import type { Data, Layout } from "plotly.js";

import type { Pitch } from "../types/api";
import {
  baseLayout,
  groupByPitchType,
  pitchColor,
  plotConfig,
} from "./chartHelpers";

interface VelocityByInningChartProps {
  pitches: Pitch[];
}

export default function VelocityByInningChart({
  pitches,
}: VelocityByInningChartProps) {
  const validPitches = useMemo(
    () =>
      pitches.filter(
        (pitch) => pitch.inning !== null && pitch.velocity !== null,
      ),
    [pitches],
  );

  const data = useMemo<Data[]>(
    () =>
      [...groupByPitchType(validPitches)].map(([pitchType, group]) => {
        const innings = new Map<number, number[]>();
        group.forEach((pitch) => {
          const inning = pitch.inning as number;
          const velocities = innings.get(inning) ?? [];
          velocities.push(pitch.velocity as number);
          innings.set(inning, velocities);
        });
        const points = [...innings.entries()].sort((a, b) => a[0] - b[0]);

        return {
          type: "scatter",
          mode: "lines+markers",
          name: pitchType,
          x: points.map(([inning]) => inning),
          y: points.map(([, velocities]) =>
            velocities.reduce((sum, value) => sum + value, 0) / velocities.length,
          ),
          customdata: points.map(([, velocities]) => velocities.length),
          line: { color: pitchColor(pitchType), width: 2 },
          marker: { color: pitchColor(pitchType), size: 7 },
          hovertemplate:
            `${pitchType}<br>Inning %{x}<br>Average: %{y:.1f} mph<br>` +
            "%{customdata} pitches<extra></extra>",
        };
      }),
    [validPitches],
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
      {validPitches.length ? (
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
        Each point is the average velocity for that pitch type and inning.
      </p>
    </section>
  );
}
