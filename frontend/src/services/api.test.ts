import { afterEach, describe, expect, it, vi } from "vitest";

import { createPlaylist, getPitches } from "./api";
import type { PitchSearchFilters } from "../types/api";

function mockJsonResponse(body: unknown, status = 200): Response {
  return {
    ok: status >= 200 && status < 300,
    status,
    json: vi.fn().mockResolvedValue(body),
  } as unknown as Response;
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("API service", () => {
  it("serializes active pitch filters and omits empty values", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      mockJsonResponse({ total: 0, limit: 100, offset: 0, pitches: [] }),
    );
    vi.stubGlobal("fetch", fetchMock);
    const filters: PitchSearchFilters = {
      pitcher_id: 7,
      game_pk: null,
      batter_side: "R",
      pitch_type: "SL",
      balls: 1,
      strikes: 2,
      result: "",
      min_velocity: 82,
      max_velocity: null,
      min_plate_x: null,
      max_plate_x: null,
      min_plate_z: null,
      max_plate_z: null,
      video_available: true,
      limit: 100,
      offset: 0,
    };

    await getPitches(filters);

    const requestUrl = String(fetchMock.mock.calls[0][0]);
    expect(requestUrl).toContain("/pitches?");
    expect(requestUrl).toContain("pitcher_id=7");
    expect(requestUrl).toContain("pitch_type=SL");
    expect(requestUrl).toContain("balls=1");
    expect(requestUrl).toContain("strikes=2");
    expect(requestUrl).toContain("video_available=true");
    expect(requestUrl).not.toContain("game_pk");
    expect(requestUrl).not.toContain("result=");
  });

  it("surfaces the backend's readable error detail", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        mockJsonResponse({ detail: "Pitcher 999 was not found." }, 404),
      ),
    );

    await expect(
      getPitches({
        pitcher_id: 999,
        game_pk: null,
        batter_side: "",
        pitch_type: "",
        balls: null,
        strikes: null,
        result: "",
        min_velocity: null,
        max_velocity: null,
        min_plate_x: null,
        max_plate_x: null,
        min_plate_z: null,
        max_plate_z: null,
        video_available: null,
        limit: 100,
        offset: 0,
      }),
    ).rejects.toThrow("Pitcher 999 was not found.");
  });

  it("creates a playlist with JSON and the POST method", async () => {
    const saved = {
      playlist_id: 3,
      playlist_name: "Two-strike breaking balls",
      description: null,
      created_at: "2026-09-07T12:00:00-04:00",
    };
    const fetchMock = vi.fn().mockResolvedValue(mockJsonResponse(saved, 201));
    vi.stubGlobal("fetch", fetchMock);

    await createPlaylist({
      playlist_name: "Two-strike breaking balls",
      description: null,
    });

    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringMatching(/\/playlists$/),
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({
          playlist_name: "Two-strike breaking balls",
          description: null,
        }),
      }),
    );
  });
});
