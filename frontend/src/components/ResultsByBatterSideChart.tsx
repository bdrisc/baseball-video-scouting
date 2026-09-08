import { useMemo } from "react";
import Plot from "react-plotly.js";
import type { Data, Layout } from "plotly.js";

import type { Pitch } from "../types/api";
import { baseLayout, plotConfig } from "./chartHelpers";

interface ResultsByBatterSideChartProps {
  pitches: Pitch[];
}

const RESULT_GROUPS = ["Ball", "Called strike", "Whiff", "Foul", "In play", "Other"];
const RESULT_COLORS: Record<string, string> = {
  Ball: "#9ba5ae",
  "Called strike": "#3676b8",
  Whiff: "#7a0019",
  Foul: "#c69212",
  "In play": "#21845a",
  Other: "#725d78",
};

function resultGroup(description: string | null): string {
  if (!description) return "Other";
  if (["swinging_strike", "swinging_strike_blocked", "missed_bunt"].includes(description)) {
    return "Whiff";
  }
  if (description === "called_strike") return "Called strike";
  if (description.includes("foul")) return "Foul";
  if (description.startsWith("hit_into_play") || description.startsWith("in_play")) {
    return "In play";
  }
  if (description === "ball" || description === "blocked_ball" || description === "pitchout") {
    return "Ball";
  }
  return "Other";
}

export default function ResultsByBatterSideChart({
  pitches,
}: ResultsByBatterSideChartProps) {
  const validPitches = useMemo(
    () => pitches.filter((pitch) => pitch.batter_side === "L" || pitch.batter_side === "R"),
    [pitches],
  );

  const data = useMemo<Data[]>(() => {
    const sides: Array<"L" | "R"> = ["L", "R"];
    const totals = sides.map(
      (side) => validPitches.filter((pitch) => pitch.batter_side === side).length,
    );

    return RESULT_GROUPS.map((group) => {
      const counts = sides.map(
        (side) =>
          validPitches.filter(
            (pitch) =>
              pitch.batter_side === side && resultGroup(pitch.description) === group,
          ).length,
      );
      return {
        type: "bar",
        name: group,
        x: ["Left-handed", "Right-handed"],
        y: counts.map((count, index) =>
          totals[index] ? (count / totals[index]) * 100 : 0,
        ),
        customdata: counts,
        marker: { color: RESULT_COLORS[group] },
        hovertemplate:
          `${group}<br>%{x}<br>%{y:.1f}% · %{customdata} pitches<extra></extra>`,
      };
    });
  }, [validPitches]);

  const layout = useMemo<Partial<Layout>>(
    () => ({
      ...baseLayout,
      margin: { l: 50, r: 16, t: 14, b: 44 },
      barmode: "stack",
      legend: { orientation: "h", x: 0, y: 1.18, font: { size: 9 } },
      xaxis: { title: { text: "Batter side" }, fixedrange: true },
      yaxis: {
        title: { text: "Share of pitches (%)" },
        range: [0, 100],
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
          <p className="eyebrow">Handedness splits</p>
          <h2>Results by batter side</h2>
        </div>
        <span className="result-count">{validPitches.length} pitches</span>
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
          <strong>No batter-side data</strong>
          <span>The current pitches do not include batter handedness.</span>
        </div>
      )}
      <p className="chart-caption">
        Result categories are shown as a percentage of pitches to each side.
      </p>
    </section>
  );
}
