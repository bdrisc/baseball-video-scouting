import { useMemo } from "react";
import Plot from "react-plotly.js";
import type { Data, Layout } from "plotly.js";

import type { Pitch } from "../types/api";
import { baseLayout, groupByPitchType, plotConfig } from "./chartHelpers";

interface UsageByCountChartProps {
  pitches: Pitch[];
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

export default function UsageByCountChart({ pitches }: UsageByCountChartProps) {
  const pitchTypes = useMemo(
    () => [...groupByPitchType(pitches)].map(([pitchType]) => pitchType),
    [pitches],
  );

  const data = useMemo<Data[]>(() => {
    const countTotals = new Map<string, number>();
    pitches.forEach((pitch) => {
      const count = `${pitch.balls}-${pitch.strikes}`;
      countTotals.set(count, (countTotals.get(count) ?? 0) + 1);
    });

    const counts = pitchTypes.map((pitchType) =>
      COUNT_ORDER.map(
        (count) =>
          pitches.filter(
            (pitch) =>
              pitch.pitch_type === pitchType &&
              `${pitch.balls}-${pitch.strikes}` === count,
          ).length,
      ),
    );
    const percentages = counts.map((row) =>
      row.map((count, index) => {
        const total = countTotals.get(COUNT_ORDER[index]) ?? 0;
        return total ? (count / total) * 100 : 0;
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
  }, [pitches, pitchTypes]);

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
      {pitches.length && pitchTypes.length ? (
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
        Each column shows pitch-type usage within that count.
      </p>
    </section>
  );
}
