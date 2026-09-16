import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import PitchTable from "./PitchTable";
import { makePitch } from "../test/fixtures";

describe("PitchTable", () => {
  const fastball = makePitch();
  const slider = makePitch({
    pitch_id: "824566_8_2",
    pitch_number: 2,
    pitch_type: "SL",
    batter_name: "Slider Batter",
    description: "swinging_strike",
    velocity: 85.2,
  });

  it("searches loaded rows and selects the matching pitch", async () => {
    const user = userEvent.setup();
    const onSelect = vi.fn();
    render(
      <PitchTable
        pitches={[fastball, slider]}
        totalMatches={2}
        limit={100}
        offset={0}
        sortBy="game_date"
        sortOrder="asc"
        loading={false}
        selectedPitchId={null}
        stagedPitchIds={[]}
        onSelect={onSelect}
        onAddToPlaylist={vi.fn()}
        onPageChange={vi.fn()}
        onPageSizeChange={vi.fn()}
        onSortChange={vi.fn()}
      />,
    );

    expect(screen.getByText("2 matches")).toBeInTheDocument();
    await user.type(screen.getByRole("searchbox"), "Slider Batter");
    expect(screen.getByText("1 visible · 2 loaded")).toBeInTheDocument();
    expect(screen.queryByText("Test Batter")).not.toBeInTheDocument();

    await user.click(screen.getByText("Slider Batter"));
    expect(onSelect).toHaveBeenCalledWith(slider);
  });

  it("adds a pitch without also selecting its table row", async () => {
    const user = userEvent.setup();
    const onSelect = vi.fn();
    const onAdd = vi.fn();
    render(
      <PitchTable
        pitches={[fastball]}
        totalMatches={1}
        limit={100}
        offset={0}
        sortBy="game_date"
        sortOrder="asc"
        loading={false}
        selectedPitchId={null}
        stagedPitchIds={[]}
        onSelect={onSelect}
        onAddToPlaylist={onAdd}
        onPageChange={vi.fn()}
        onPageSizeChange={vi.fn()}
        onSortChange={vi.fn()}
      />,
    );

    await user.click(screen.getByRole("button", { name: "+ Add" }));
    expect(onAdd).toHaveBeenCalledWith(fastball);
    expect(onSelect).not.toHaveBeenCalled();
  });

  it("requests server-side sorting and the next page", async () => {
    const user = userEvent.setup();
    const onPageChange = vi.fn();
    const onSortChange = vi.fn();
    render(
      <PitchTable
        pitches={[fastball, slider]}
        totalMatches={202}
        limit={100}
        offset={0}
        sortBy="game_date"
        sortOrder="asc"
        loading={false}
        selectedPitchId={null}
        stagedPitchIds={[]}
        onSelect={vi.fn()}
        onAddToPlaylist={vi.fn()}
        onPageChange={onPageChange}
        onPageSizeChange={vi.fn()}
        onSortChange={onSortChange}
      />,
    );

    await user.click(screen.getByRole("button", { name: "Sort by Velocity ascending" }));
    expect(onSortChange).toHaveBeenCalledWith("velocity", "asc");

    await user.click(screen.getByRole("button", { name: "Next" }));
    expect(onPageChange).toHaveBeenCalledWith(100);
    expect(screen.getByText("Page 1 of 3")).toBeInTheDocument();
  });
});
