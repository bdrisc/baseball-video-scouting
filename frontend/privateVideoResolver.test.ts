import { describe, expect, it, vi } from "vitest";

import { extractOfficialClip, resolveOfficialClip } from "./privateVideoResolver";

const playId = "20734eca-78c3-31a8-93dd-acafae5b10bc";
const html = `<video id="sporty" classid="${playId}"><source src="https://sporty-clips.mlb.com/clip.mp4" type="video/mp4"></video>`;

describe("official clip lookup", () => {
  it("accepts only the selected pitch and official media host", () => {
    expect(extractOfficialClip(html, playId)).toBe("https://sporty-clips.mlb.com/clip.mp4");
    expect(extractOfficialClip(html, "1b470dae-208b-3c4c-8e34-32bd7cda5597")).toBeNull();
    expect(extractOfficialClip(html.replace("sporty-clips.mlb.com", "clips.example.com"), playId)).toBeNull();
  });

  it("requests only the selected official page and reads its video source", async () => {
    const fetcher = vi.fn(async (_url: string) => new Response(html, {
      headers: { "content-type": "text/html; charset=utf-8" },
    }));
    expect(await resolveOfficialClip(playId, fetcher as typeof fetch)).toBe("https://sporty-clips.mlb.com/clip.mp4");
    expect(fetcher.mock.calls[0]?.[0]).toBe(
      `https://baseballsavant.mlb.com/sporty-videos?playId=${playId}`,
    );
    expect(await resolveOfficialClip("../unsafe", fetcher as typeof fetch)).toBeNull();
    expect(fetcher).toHaveBeenCalledTimes(1);
  });
});
