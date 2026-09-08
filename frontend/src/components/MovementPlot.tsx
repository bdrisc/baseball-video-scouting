import { useMemo } from "react";
import Plot from "react-plotly.js";
import type { Data, Layout, PlotMouseEvent } from "plotly.js";

import type { Pitch } from "../types/api";
import {
  baseLayout,
  chartPitchFromClick,
  groupByPitchType,
  pitchColor,
  pitchLabel,
  plotConfig,
} from "./chartHelpers";

interface MovementPlotProps {
  pitches: Pitch[];
  selectedPitchId: string | null;
  onSelect: (pitch: Pitch) => void;
}

export default function MovementPlot({
  pitches,
  selectedPitchId,
  onSelect,
}: MovementPlotProps) {
  const chartPitches = useMemo(
    () =>
      pitches.filter(
        (pitch) =>
          pitch.horizontal_break !== null && pitch.vertical_break !== null,
      ),
    [pitches],
  );

  const traces = useMemo<Data[]>(
    () =>
      [...groupByPitchType(chartPitches)].map(([pitchType, group]) => ({
        type: "scatter",
        mode: "markers",
        name: pitchType,
        x: group.map((pitch) => (pitch.horizontal_break as number) * 12),
        y: group.map((pitch) => (pitch.vertical_break as number) * 12),
        customdata: group.map((pitch) => pitch.pitch_id),
        text: group.map(
          (pitch) =>
            `${pitchLabel(pitch.pitch_type)} · ${pitch.velocity?.toFixed(1) ?? "—"} mph<br>` +
            `${pitch.batter_name ?? "Unknown batter"} · ${pitch.balls}-${pitch.strikes}`,
        ),
        hovertemplate:
          "%{text}<br>Break: %{x:.1f} H, %{y:.1f} V in<extra></extra>",
        marker: {
          color: pitchColor(pitchType),
          opacity: 0.82,
          size: group.map((pitch) =>
            pitch.pitch_id === selectedPitchId ? 13 : 8,
          ),
          line: {
            color: group.map((pitch) =>
              pitch.pitch_id === selectedPitchId ? "#17202a" : "#ffffff",
            ),
            width: group.map((pitch) =>
              pitch.pitch_id === selectedPitchId ? 3 : 1,
            ),
          },
        },
      })),
    [chartPitches, selectedPitchId],
  );

  const layout = useMemo<Partial<Layout>>(
    () => ({
      ...baseLayout,
      showlegend: true,
      legend: {
        orientation: "h",
        x: 0,
        y: 1.12,
        font: { size: 10 },
      },
      xaxis: {
        title: { text: "Horizontal break (in)" },
        fixedrange: true,
        zeroline: true,
        zerolinewidth: 1,
        zerolinecolor: "#9da7b0",
        gridcolor: "#e7eaed",
      },
      yaxis: {
        title: { text: "Induced vertical break (in)" },
        fixedrange: true,
        zeroline: true,
        zerolinewidth: 1,
        zerolinecolor: "#9da7b0",
        gridcolor: "#e7eaed",
      },
    }),
    [],
  );

  function handleClick(event: PlotMouseEvent) {
    const pitch = chartPitchFromClick(event.points[0]?.customdata, chartPitches);
    if (pitch) onSelect(pitch);
  }

  return (
    <section className="panel chart-card">
      <div className="panel-heading">
        <div>
          <p className="eyebrow">Pitch shape</p>
          <h2>Movement profile</h2>
        </div>
        <span className="result-count">{chartPitches.length} pitches</span>
      </div>
      {chartPitches.length ? (
        <div className="plot-container tall-plot">
          <Plot
            data={traces}
            layout={layout}
            config={plotConfig}
            useResizeHandler
            style={{ width: "100%", height: "100%" }}
            onClick={handleClick}
          />
        </div>
      ) : (
        <div className="empty-state chart-empty">
          <strong>No movement data</strong>
          <span>No loaded pitches contain horizontal and vertical break.</span>
        </div>
      )}
      <p className="chart-caption">
        Savant movement converted from feet to inches. Click a pitch to select it.
      </p>
    </section>
  );
}
