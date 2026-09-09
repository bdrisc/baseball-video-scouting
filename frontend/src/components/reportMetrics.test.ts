import { describe, expect, it } from "vitest";

import { buildReportMetrics } from "./reportMetrics";
import { makePitch } from "../test/fixtures";

describe("buildReportMetrics", () => {
  it("calculates arsenal, two-strike, handedness, location, and damage metrics", () => {
    const pitches = [
      makePitch(),
      makePitch({
        pitch_id: "824566_8_2",
        pitch_number: 2,
        pitch_type: "SL",
        velocity: 85,
        batter_side: "L",
        balls: 0,
        strikes: 2,
        description: "swinging_strike",
        events: "home_run",
        plate_x: 1.2,
        plate_z: 1.1,
        exit_velocity: 100,
        launch_angle: 28,
      }),
    ];

    const metrics = buildReportMetrics(pitches);

    expect(metrics.arsenal).toHaveLength(2);
    expect(metrics.arsenal.map((row) => row.usage)).toEqual([50, 50]);
    expect(metrics.usageSummary).toBe("FF 50.0% · SL 50.0%");
    expect(metrics.handedness[0].pitchMix).toEqual([
      { pitchType: "SL", usage: 100 },
    ]);
    expect(metrics.handedness[0].whiffRate).toBe(100);
    expect(metrics.handedness[0].zoneRate).toBe(0);
    expect(metrics.putaway.sampleSize).toBe(1);
    expect(metrics.putaway.topPitch).toBe("SL");
    expect(metrics.putaway.whiffRate).toBe(100);
    expect(metrics.location.zoneRate).toBe(50);
    expect(metrics.damage.hardHitRate).toBe(100);
    expect(metrics.damage.mostDamagedPitch).toBe("SL");
  });

  it("includes every pitch type in the usage summary", () => {
    const pitches = ["FF", "CH", "SI", "SL", "CU"].map(
      (pitchType, index) =>
        makePitch({
          pitch_id: `824566_8_${index + 1}`,
          pitch_number: index + 1,
          pitch_type: pitchType,
        }),
    );

    expect(buildReportMetrics(pitches).usageSummary).toBe(
      "FF 20.0% · CH 20.0% · SI 20.0% · SL 20.0% · CU 20.0%",
    );
  });
});
