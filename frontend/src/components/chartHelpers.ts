import type { Config, Layout } from "plotly.js";

import type { Pitch } from "../types/api";

export const PITCH_COLORS: Record<string, string> = {
  FF: "#c62828",
  FA: "#c62828",
  SI: "#e87916",
  FT: "#e87916",
  FC: "#8a2636",
  SL: "#c69212",
  ST: "#b59a18",
  CU: "#3676b8",
  KC: "#4b8ed2",
  CH: "#21845a",
  FS: "#2f9b75",
  SP: "#168a8a",
  KN: "#7757a8",
};

export const PITCH_NAMES: Record<string, string> = {
  FF: "Four-seam",
  FA: "Fastball",
  SI: "Sinker",
  FT: "Two-seam",
  FC: "Cutter",
  SL: "Slider",
  ST: "Sweeper",
  CU: "Curveball",
  KC: "Knuckle curve",
  CH: "Changeup",
  FS: "Splitter",
  SP: "Splitter",
  KN: "Knuckleball",
};

export const plotConfig: Partial<Config> = {
  displaylogo: false,
  responsive: true,
  scrollZoom: false,
};

export const baseLayout: Partial<Layout> = {
  autosize: true,
  margin: { l: 54, r: 20, t: 16, b: 50 },
  paper_bgcolor: "rgba(0,0,0,0)",
  plot_bgcolor: "#fafbfc",
  font: {
    family:
      'Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif',
    color: "#3c4650",
    size: 11,
  },
  hoverlabel: {
    bgcolor: "#17202a",
    bordercolor: "#17202a",
    font: { color: "#ffffff", size: 12 },
  },
};

export function pitchColor(pitchType: string): string {
  return PITCH_COLORS[pitchType] ?? "#68737e";
}

export function pitchLabel(pitchType: string): string {
  return PITCH_NAMES[pitchType] ?? pitchType;
}

export function groupByPitchType(pitches: Pitch[]): Map<string, Pitch[]> {
  const groups = new Map<string, Pitch[]>();

  pitches.forEach((pitch) => {
    const group = groups.get(pitch.pitch_type) ?? [];
    group.push(pitch);
    groups.set(pitch.pitch_type, group);
  });

  return new Map(
    [...groups.entries()].sort((a, b) => b[1].length - a[1].length),
  );
}

export function chartPitchFromClick(
  customData: unknown,
  pitches: Pitch[],
): Pitch | null {
  const pitchId = Array.isArray(customData) ? customData[0] : customData;
  if (typeof pitchId !== "string") return null;
  return pitches.find((pitch) => pitch.pitch_id === pitchId) ?? null;
}

export function readableResult(value: string | null): string {
  if (!value) return "Unknown";
  return value
    .replaceAll("_", " ")
    .replace(/\b\w/g, (letter) => letter.toUpperCase());
}
