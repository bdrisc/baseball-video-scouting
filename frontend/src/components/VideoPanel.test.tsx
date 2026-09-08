import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import VideoPanel from "./VideoPanel";
import { makePitch } from "../test/fixtures";

describe("VideoPanel", () => {
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
});
