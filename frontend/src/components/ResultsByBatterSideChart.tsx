import { useMemo } from "react";
import Plot from "react-plotly.js";
import type { Data, Layout } from "plotly.js";

import type {
  BatterSideResultAggregate,
  ResultGroup,
} from "../types/api";
import { baseLayout, plotConfig } from "./chartHelpers";

interface ResultsByBatterSideChartProps {
  rows: BatterSideResultAggregate[];
}

const RESULT_GROUPS: ResultGroup[] = [
  "Ball",
  "Called strike",
  "Whiff",
  "Foul",
  "In play",
  "Other",
];
const RESULT_COLORS: Record<string, string> = {
  Ball: "#9ba5ae",
  "Called strike": "#3676b8",
  Whiff: "#7a0019",
  Foul: "#c69212",
  "In play": "#21845a",
  Other: "#725d78",
};

export default function ResultsByBatterSideChart({
  rows,
}: ResultsByBatterSideChartProps) {
  const data = useMemo<Data[]>(() => {
    const sides: Array<"L" | "R"> = ["L", "R"];

    return RESULT_GROUPS.map((group) => {
      const matches = sides.map((side) =>
        rows.find(
          (row) => row.batter_side === side && row.result_group === group,
        ),
      );
      return {
        type: "bar",
        name: group,
        x: ["Left-handed", "Right-handed"],
        y: matches.map((row) => row?.percentage ?? 0),
        customdata: matches.map((row) => row?.pitch_count ?? 0),
        marker: { color: RESULT_COLORS[group] },
        hovertemplate:
          `${group}<br>%{x}<br>%{y:.1f}% · %{customdata} pitches<extra></extra>`,
      };
    });
  }, [rows]);

  const total = rows.reduce((sum, row) => sum + row.pitch_count, 0);

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
        <span className="result-count">{total} pitches</span>
      </div>
      {total ? (
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
        Result categories use the complete filtered result and are shown as a
        percentage of pitches to each side.
      </p>
    </section>
  );
}
