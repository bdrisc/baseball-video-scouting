import type { Pitch } from "../types/api";

const WHIFFS = new Set(["swinging_strike", "swinging_strike_blocked", "missed_bunt"]);
const SWINGS = new Set([
  ...WHIFFS,
  "foul",
  "foul_tip",
  "foul_bunt",
  "bunt_foul_tip",
  "hit_into_play",
  "hit_into_play_no_out",
  "hit_into_play_score",
]);

export interface ArsenalRow {
  pitchType: string;
  count: number;
  usage: number;
  averageVelocity: number | null;
  averageSpin: number | null;
  horizontalBreak: number | null;
  verticalBreak: number | null;
  whiffRate: number | null;
  zoneRate: number | null;
}

export interface TendencyRow {
  label: string;
  sampleSize: number;
  topPitch: string;
  usage: number | null;
}

export interface HandednessRow {
  side: "L" | "R";
  count: number;
  topPitch: string;
  topPitchUsage: number | null;
  whiffRate: number | null;
  averageVelocity: number | null;
}

export interface ReportMetrics {
  arsenal: ArsenalRow[];
  usageSummary: string;
  countTendencies: TendencyRow[];
  handedness: HandednessRow[];
  location: {
    sampleSize: number;
    zoneRate: number | null;
    primaryVerticalBand: string;
    primaryHorizontalLane: string;
    fastballElevatedRate: number | null;
  };
  putaway: {
    sampleSize: number;
    topPitch: string;
    topPitchUsage: number | null;
    whiffRate: number | null;
    strikeouts: number;
    bestWhiffPitch: string;
  };
  damage: {
    ballsInPlay: number;
    averageExitVelocity: number | null;
    hardHitRate: number | null;
    maximumExitVelocity: number | null;
    homeRuns: number;
    mostDamagedPitch: string;
  };
}

function average(values: Array<number | null>): number | null {
  const validValues = values.filter((value): value is number => value !== null);
  if (!validValues.length) return null;
  return validValues.reduce((sum, value) => sum + value, 0) / validValues.length;
}

function rate(numerator: number, denominator: number): number | null {
  return denominator ? (numerator / denominator) * 100 : null;
}

function isWhiff(pitch: Pitch): boolean {
  return WHIFFS.has(pitch.description ?? "");
}

function isSwing(pitch: Pitch): boolean {
  const description = pitch.description ?? "";
  return SWINGS.has(description) || description.startsWith("in_play");
}

function isInZone(pitch: Pitch): boolean {
  return (
    pitch.plate_x !== null &&
    pitch.plate_z !== null &&
    Math.abs(pitch.plate_x) <= 0.83 &&
    pitch.plate_z >= 1.5 &&
    pitch.plate_z <= 3.5
  );
}

function topPitch(pitches: Pitch[]): { pitchType: string; usage: number | null } {
  if (!pitches.length) return { pitchType: "—", usage: null };
  const counts = new Map<string, number>();
  pitches.forEach((pitch) =>
    counts.set(pitch.pitch_type, (counts.get(pitch.pitch_type) ?? 0) + 1),
  );
  const [pitchType, count] = [...counts.entries()].sort((a, b) => b[1] - a[1])[0];
  return { pitchType, usage: rate(count, pitches.length) };
}

function mostCommon(values: string[]): string {
  if (!values.length) return "—";
  const counts = new Map<string, number>();
  values.forEach((value) => counts.set(value, (counts.get(value) ?? 0) + 1));
  return [...counts.entries()].sort((a, b) => b[1] - a[1])[0][0];
}

function verticalBand(z: number): string {
  if (z > 3.5) return "Above zone";
  if (z >= 2.83) return "Upper third";
  if (z >= 2.17) return "Middle third";
  if (z >= 1.5) return "Lower third";
  return "Below zone";
}

function horizontalLane(x: number): string {
  if (x < -0.83) return "Left off plate";
  if (x < -0.28) return "Left third";
  if (x <= 0.28) return "Center third";
  if (x <= 0.83) return "Right third";
  return "Right off plate";
}

export function buildReportMetrics(pitches: Pitch[]): ReportMetrics {
  const pitchTypes = new Map<string, Pitch[]>();
  pitches.forEach((pitch) => {
    const group = pitchTypes.get(pitch.pitch_type) ?? [];
    group.push(pitch);
    pitchTypes.set(pitch.pitch_type, group);
  });

  const arsenal = [...pitchTypes.entries()]
    .map(([pitchType, group]): ArsenalRow => {
      const swings = group.filter(isSwing);
      const located = group.filter(
        (pitch) => pitch.plate_x !== null && pitch.plate_z !== null,
      );
      return {
        pitchType,
        count: group.length,
        usage: rate(group.length, pitches.length) ?? 0,
        averageVelocity: average(group.map((pitch) => pitch.velocity)),
        averageSpin: average(group.map((pitch) => pitch.spin_rate)),
        horizontalBreak: average(group.map((pitch) => pitch.horizontal_break)),
        verticalBreak: average(group.map((pitch) => pitch.vertical_break)),
        whiffRate: rate(swings.filter(isWhiff).length, swings.length),
        zoneRate: rate(located.filter(isInZone).length, located.length),
      };
    })
    .sort((a, b) => b.count - a.count);

  const usageSummary = arsenal.length
    ? arsenal
        .slice(0, 3)
        .map((pitch) => `${pitch.pitchType} ${pitch.usage.toFixed(1)}%`)
        .join(" · ")
    : "—";

  const countGroups: Array<[string, (pitch: Pitch) => boolean]> = [
    ["First pitch", (pitch) => pitch.balls === 0 && pitch.strikes === 0],
    ["Pitcher ahead", (pitch) => pitch.strikes > pitch.balls],
    ["Hitter ahead", (pitch) => pitch.balls > pitch.strikes],
    ["Two strikes", (pitch) => pitch.strikes === 2],
    ["Full count", (pitch) => pitch.balls === 3 && pitch.strikes === 2],
  ];
  const countTendencies = countGroups.map(([label, test]) => {
    const sample = pitches.filter(test);
    const primary = topPitch(sample);
    return {
      label,
      sampleSize: sample.length,
      topPitch: primary.pitchType,
      usage: primary.usage,
    };
  });

  const handedness = (["L", "R"] as const).map((side): HandednessRow => {
    const sample = pitches.filter((pitch) => pitch.batter_side === side);
    const swings = sample.filter(isSwing);
    const primary = topPitch(sample);
    return {
      side,
      count: sample.length,
      topPitch: primary.pitchType,
      topPitchUsage: primary.usage,
      whiffRate: rate(swings.filter(isWhiff).length, swings.length),
      averageVelocity: average(sample.map((pitch) => pitch.velocity)),
    };
  });

  const located = pitches.filter(
    (pitch) => pitch.plate_x !== null && pitch.plate_z !== null,
  );
  const fastballs = located.filter((pitch) =>
    ["FF", "FA", "SI", "FT", "FC"].includes(pitch.pitch_type),
  );
  const elevatedFastballs = fastballs.filter(
    (pitch) => (pitch.plate_z as number) >= 2.83,
  );

  const twoStrikePitches = pitches.filter((pitch) => pitch.strikes === 2);
  const twoStrikeSwings = twoStrikePitches.filter(isSwing);
  const twoStrikePrimary = topPitch(twoStrikePitches);
  const whiffByPitch = [...pitchTypes.entries()]
    .map(([pitchType, group]) => {
      const sample = group.filter((pitch) => pitch.strikes === 2 && isSwing(pitch));
      return {
        pitchType,
        whiffs: sample.filter(isWhiff).length,
        whiffRate: rate(sample.filter(isWhiff).length, sample.length) ?? -1,
      };
    })
    .filter((row) => row.whiffs > 0)
    .sort((a, b) => b.whiffRate - a.whiffRate || b.whiffs - a.whiffs);

  const ballsInPlay = pitches.filter((pitch) => pitch.exit_velocity !== null);
  const hardHits = ballsInPlay.filter((pitch) => (pitch.exit_velocity as number) >= 95);
  const damageByPitch = [...pitchTypes.entries()]
    .map(([pitchType, group]) => ({
      pitchType,
      values: group
        .map((pitch) => pitch.exit_velocity)
        .filter((value): value is number => value !== null),
    }))
    .filter((row) => row.values.length)
    .map((row) => ({
      pitchType: row.pitchType,
      average: row.values.reduce((sum, value) => sum + value, 0) / row.values.length,
      count: row.values.length,
    }))
    .sort((a, b) => b.average - a.average || b.count - a.count);

  return {
    arsenal,
    usageSummary,
    countTendencies,
    handedness,
    location: {
      sampleSize: located.length,
      zoneRate: rate(located.filter(isInZone).length, located.length),
      primaryVerticalBand: mostCommon(
        located.map((pitch) => verticalBand(pitch.plate_z as number)),
      ),
      primaryHorizontalLane: mostCommon(
        located.map((pitch) => horizontalLane(pitch.plate_x as number)),
      ),
      fastballElevatedRate: rate(elevatedFastballs.length, fastballs.length),
    },
    putaway: {
      sampleSize: twoStrikePitches.length,
      topPitch: twoStrikePrimary.pitchType,
      topPitchUsage: twoStrikePrimary.usage,
      whiffRate: rate(twoStrikeSwings.filter(isWhiff).length, twoStrikeSwings.length),
      strikeouts: twoStrikePitches.filter((pitch) =>
        (pitch.events ?? "").includes("strikeout"),
      ).length,
      bestWhiffPitch: whiffByPitch[0]?.pitchType ?? "—",
    },
    damage: {
      ballsInPlay: ballsInPlay.length,
      averageExitVelocity: average(ballsInPlay.map((pitch) => pitch.exit_velocity)),
      hardHitRate: rate(hardHits.length, ballsInPlay.length),
      maximumExitVelocity: ballsInPlay.length
        ? Math.max(...ballsInPlay.map((pitch) => pitch.exit_velocity as number))
        : null,
      homeRuns: pitches.filter((pitch) => pitch.events === "home_run").length,
      mostDamagedPitch: damageByPitch[0]?.pitchType ?? "—",
    },
  };
}
