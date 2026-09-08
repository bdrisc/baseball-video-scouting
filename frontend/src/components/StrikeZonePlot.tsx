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
  readableResult,
} from "./chartHelpers";

interface StrikeZonePlotProps {
  pitches: Pitch[];
  selectedPitchId: string | null;
  onSelect: (pitch: Pitch) => void;
}

export default function StrikeZonePlot({
  pitches,
  selectedPitchId,
  onSelect,
}: StrikeZonePlotProps) {
  const chartPitches = useMemo(
    () =>
      pitches.filter(
        (pitch) => pitch.plate_x !== null && pitch.plate_z !== null,
      ),
    [pitches],
  );

  const traces = useMemo<Data[]>(
    () =>
      [...groupByPitchType(chartPitches)].map(([pitchType, group]) => ({
        type: "scatter",
        mode: "markers",
        name: pitchType,
        x: group.map((pitch) => pitch.plate_x as number),
        y: group.map((pitch) => pitch.plate_z as number),
        customdata: group.map((pitch) => pitch.pitch_id),
        text: group.map(
          (pitch) =>
            `${pitchLabel(pitch.pitch_type)} · ${pitch.velocity?.toFixed(1) ?? "—"} mph<br>` +
            `${pitch.batter_name ?? "Unknown batter"} · ${pitch.balls}-${pitch.strikes}<br>` +
            readableResult(pitch.description ?? pitch.events),
        ),
        hovertemplate:
          "%{text}<br>Location: %{x:.2f}, %{y:.2f} ft<extra></extra>",
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
        title: { text: "Horizontal location (ft)" },
        range: [-2.25, 2.25],
        fixedrange: true,
        zeroline: true,
        zerolinecolor: "#c5cbd1",
        gridcolor: "#e7eaed",
      },
      yaxis: {
        title: { text: "Height (ft)" },
        range: [0, 5],
        fixedrange: true,
        gridcolor: "#e7eaed",
      },
      shapes: [
        {
          type: "rect",
          x0: -0.83,
          x1: 0.83,
          y0: 1.5,
          y1: 3.5,
          line: { color: "#7a0019", width: 2 },
          fillcolor: "rgba(122, 0, 25, 0.025)",
        },
        ...[-0.277, 0.277].map((x) => ({
          type: "line" as const,
          x0: x,
          x1: x,
          y0: 1.5,
          y1: 3.5,
          line: { color: "rgba(122, 0, 25, 0.25)", width: 1 },
        })),
        ...[2.167, 2.833].map((y) => ({
          type: "line" as const,
          x0: -0.83,
          x1: 0.83,
          y0: y,
          y1: y,
          line: { color: "rgba(122, 0, 25, 0.25)", width: 1 },
        })),
      ],
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
          <p className="eyebrow">Location</p>
          <h2>Strike zone</h2>
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
          <strong>No location data</strong>
          <span>No loaded pitches contain plate coordinates.</span>
        </div>
      )}
      <p className="chart-caption">
        Catcher-view Savant coordinates. Click a pitch to select its table row.
      </p>
    </section>
  );
}
