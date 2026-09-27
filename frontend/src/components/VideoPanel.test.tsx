import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import VideoPanel from "./VideoPanel";
import { makePitch } from "../test/fixtures";

describe("VideoPanel", () => {
  afterEach(() => {
    vi.unstubAllEnvs();
    vi.unstubAllGlobals();
  });

  it("opens the selected official link and navigates to the next video", async () => {
    const user = userEvent.setup();
    const first = makePitch();
    const second = makePitch({
      pitch_id: "824566_8_2",
      pitch_number: 2,
      pitch_type: "SL",
      video_url: "https://www.mlb.com/video/example-slider",
    });
    const onSelect = vi.fn();
    render(
      <VideoPanel
        pitch={first}
        pitches={[first, second]}
        stagedPitchIds={[]}
        onSelect={onSelect}
        onAddToPlaylist={vi.fn()}
        playlistReviewActive={false}
        onExitPlaylistReview={vi.fn()}
      />,
    );

    expect(screen.getByText("1 of 2")).toBeInTheDocument();
    expect(
      screen.getByRole("link", { name: /Watch in MLB Film Room/i }),
    ).toHaveAttribute("href", first.video_url);

    await user.click(screen.getByRole("button", { name: /Next video/i }));
    expect(onSelect).toHaveBeenCalledWith(second);
  });

  it("plays one configured private pitch inline and retains the official page on failure", () => {
    vi.stubEnv("VITE_AUTH_MODE", "private");
    vi.stubEnv("VITE_PRIVATE_TEST_PITCH_ID", "824566_8_1");
    vi.stubEnv("VITE_PRIVATE_TEST_VIDEO_URL", "https://sporty-clips.mlb.com/example.mp4");
    const pitch = makePitch({ video_url: "https://baseballsavant.mlb.com/sporty-videos?playId=example" });
    const props = {
      pitch, pitches: [pitch], stagedPitchIds: [], onSelect: vi.fn(),
      onAddToPlaylist: vi.fn(), playlistReviewActive: false,
      onExitPlaylistReview: vi.fn(),
    };
    const { container, rerender } = render(<VideoPanel {...props} />);

    expect(container.querySelector("video source")).toHaveAttribute(
      "src", "https://sporty-clips.mlb.com/example.mp4",
    );
    expect(screen.getByRole("link", { name: /Watch in MLB Film Room/i })).toHaveAttribute(
      "href", pitch.video_url,
    );
    fireEvent.error(container.querySelector("video")!);
    expect(container.querySelector("video")).toBeNull();
    expect(screen.getByText("Use the official MLB viewer")).toBeInTheDocument();

    rerender(<VideoPanel {...props} pitch={makePitch({ pitch_id: "824566_8_2" })} />);
    expect(container.querySelector("video")).toBeNull();
  });

  it("loads the official video URL for any selected linked pitch in private mode", async () => {
    vi.stubEnv("VITE_AUTH_MODE", "private");
    const fetcher = vi.fn(async (_url: string) => ({
      ok: true, json: async () => ({ url: "https://sporty-clips.mlb.com/another.mp4" }),
    }));
    vi.stubGlobal("fetch", fetcher);
    const pitch = makePitch({
      pitch_id: "822684_30_2",
      video_url: "https://baseballsavant.mlb.com/sporty-videos?playId=1b470dae-208b-3c4c-8e34-32bd7cda5597",
    });
    const { container } = render(<VideoPanel pitch={pitch} pitches={[pitch]}
      stagedPitchIds={[]} onSelect={vi.fn()} onAddToPlaylist={vi.fn()}
      playlistReviewActive={false} onExitPlaylistReview={vi.fn()} />);
    await waitFor(() => expect(container.querySelector("video source")).toHaveAttribute(
      "src", "https://sporty-clips.mlb.com/another.mp4",
    ));
    expect(fetcher.mock.calls[0]?.[0]).toBe(
      "/__private_video_source?playId=1b470dae-208b-3c4c-8e34-32bd7cda5597",
    );
  });
});
