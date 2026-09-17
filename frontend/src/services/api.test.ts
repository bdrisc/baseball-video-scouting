import { afterEach, describe, expect, it, vi } from "vitest";

import {
  createPlaylist,
  getPitchAggregates,
  getPitches,
  getTeams,
  searchPitchers,
} from "./api";
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
      season: 2026,
      team_id: 12,
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
      sort_by: "velocity",
      sort_order: "desc",
    };

    await getPitches(filters);

    const requestUrl = String(fetchMock.mock.calls[0][0]);
    expect(requestUrl).toContain("/pitches?");
    expect(requestUrl).toContain("pitcher_id=7");
    expect(requestUrl).toContain("season=2026");
    expect(requestUrl).toContain("team_id=12");
    expect(requestUrl).toContain("pitch_type=SL");
    expect(requestUrl).toContain("balls=1");
    expect(requestUrl).toContain("strikes=2");
    expect(requestUrl).toContain("video_available=true");
    expect(requestUrl).toContain("sort_by=velocity");
    expect(requestUrl).toContain("sort_order=desc");
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
        season: 2026,
        team_id: null,
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
        sort_by: "game_date",
        sort_order: "asc",
      }),
    ).rejects.toThrow("Pitcher 999 was not found.");
  });

  it("requests aggregates without table pagination or sorting", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      mockJsonResponse({
        total: 0,
        summary: {},
        pitch_usage: [],
        velocity_by_inning: [],
        usage_by_count: [],
        results_by_batter_side: [],
        report: {},
      }),
    );
    vi.stubGlobal("fetch", fetchMock);

    await getPitchAggregates({
      pitcher_id: 7,
      game_pk: null,
      season: 2026,
      team_id: null,
      batter_side: "R",
      pitch_type: "SL",
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
    });

    const requestUrl = String(fetchMock.mock.calls[0][0]);
    expect(requestUrl).toContain("/pitches/aggregates?");
    expect(requestUrl).toContain("pitcher_id=7");
    expect(requestUrl).toContain("batter_side=R");
    expect(requestUrl).toContain("pitch_type=SL");
    expect(requestUrl).not.toContain("limit=");
    expect(requestUrl).not.toContain("offset=");
    expect(requestUrl).not.toContain("sort_by=");
  });

  it("serializes season-wide pitcher discovery filters", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      mockJsonResponse({
        total: 1,
        limit: 50,
        offset: 0,
        has_previous: false,
        has_next: false,
        pitchers: [],
      }),
    );
    vi.stubGlobal("fetch", fetchMock);

    await searchPitchers({
      q: "messick",
      season: 2026,
      team_id: 12,
      throws: "L",
      limit: 50,
      offset: 0,
    });

    const requestUrl = String(fetchMock.mock.calls[0][0]);
    expect(requestUrl).toContain("/pitchers/search?");
    expect(requestUrl).toContain("q=messick");
    expect(requestUrl).toContain("season=2026");
    expect(requestUrl).toContain("team_id=12");
    expect(requestUrl).toContain("throws=L");
  });

  it("requests teams for the selected season", async () => {
    const fetchMock = vi.fn().mockResolvedValue(mockJsonResponse([]));
    vi.stubGlobal("fetch", fetchMock);

    await getTeams(2026);

    expect(String(fetchMock.mock.calls[0][0])).toContain("/teams?season=2026");
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
