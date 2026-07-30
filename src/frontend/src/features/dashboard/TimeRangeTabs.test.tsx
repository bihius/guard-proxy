import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";
import { describe, expect, it, vi } from "vitest";

import { TimeRangeTabs } from "./TimeRangeTabs";
import type { StatsWindow } from "./types";

/**
 * Mirrors how DashboardPage drives the control: the selection is owned by the
 * parent, so every change re-renders the surrounding tree.
 */
function Harness({ initial = "24h" as StatsWindow }) {
  const [value, setValue] = useState<StatsWindow>(initial);
  return (
    <div>
      <TimeRangeTabs value={value} onChange={setValue} />
      <button type="button">Outside</button>
    </div>
  );
}

describe("TimeRangeTabs", () => {
  it("selects a window on click", async () => {
    const user = userEvent.setup();
    render(<Harness />);

    await user.click(screen.getByRole("tab", { name: "7d" }));

    expect(screen.getByRole("tab", { name: "7d" })).toHaveAttribute(
      "aria-selected",
      "true",
    );
    expect(screen.getByRole("tab", { name: "24h" })).toHaveAttribute(
      "aria-selected",
      "false",
    );
  });

  it("keeps moving through every window on repeated arrow presses", async () => {
    const user = userEvent.setup();
    render(<Harness initial="1h" />);

    screen.getByRole("tab", { name: "1h" }).focus();

    // Walking the whole control in one go is the case that regressed in the
    // field: the first move worked and every later press did nothing.
    for (const expected of ["24h", "7d", "30d", "1h"]) {
      await user.keyboard("{ArrowRight}");
      const tab = screen.getByRole("tab", { name: expected });
      expect(tab).toHaveAttribute("aria-selected", "true");
      expect(tab).toHaveFocus();
    }
  });

  it("walks backwards and wraps around", async () => {
    const user = userEvent.setup();
    render(<Harness initial="1h" />);

    screen.getByRole("tab", { name: "1h" }).focus();
    await user.keyboard("{ArrowLeft}");

    expect(screen.getByRole("tab", { name: "30d" })).toHaveFocus();
  });

  it("jumps to the first and last window with Home and End", async () => {
    const user = userEvent.setup();
    render(<Harness />);

    screen.getByRole("tab", { name: "24h" }).focus();
    await user.keyboard("{End}");
    expect(screen.getByRole("tab", { name: "30d" })).toHaveFocus();

    await user.keyboard("{Home}");
    expect(screen.getByRole("tab", { name: "1h" })).toHaveFocus();
  });

  it("exposes only the selected tab to sequential tab order", async () => {
    render(<Harness />);

    expect(screen.getByRole("tab", { name: "24h" })).toHaveAttribute("tabindex", "0");
    expect(screen.getByRole("tab", { name: "7d" })).toHaveAttribute("tabindex", "-1");
  });

  it("does not steal focus when the window changes from elsewhere", () => {
    const onChange = vi.fn();

    const { rerender } = render(<TimeRangeTabs value="24h" onChange={onChange} />);
    render(
      <button type="button" data-testid="outside">
        Outside
      </button>,
    );

    const outside = screen.getByTestId("outside");
    outside.focus();
    expect(outside).toHaveFocus();

    // A refresh elsewhere on the page must not yank the caret into the tablist.
    rerender(<TimeRangeTabs value="7d" onChange={onChange} />);

    expect(outside).toHaveFocus();
  });
});
