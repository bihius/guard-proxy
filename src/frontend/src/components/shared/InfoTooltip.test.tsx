import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { InfoTooltip } from "./InfoTooltip";

describe("InfoTooltip", () => {
  it("exposes help text through the trigger and tooltip", () => {
    render(<InfoTooltip label="Helpful policy explanation" />);

    expect(
      screen.getByRole("button", { name: "Helpful policy explanation" }),
    ).toBeInTheDocument();
    expect(screen.getByText("Helpful policy explanation")).toBeInTheDocument();
  });
});
