import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";

describe("form controls", () => {
  it("uses muted text on input placeholders", () => {
    render(<Input aria-label="Domain" placeholder="example.com" />);

    expect(screen.getByLabelText("Domain")).toHaveClass("placeholder:text-muted-foreground");
  });

  it("sets muted colors for select text and native options", () => {
    render(
      <Select aria-label="Policy" defaultValue="">
        <option value="">None</option>
      </Select>,
    );

    expect(screen.getByLabelText("Policy")).toHaveClass(
      "text-muted-foreground",
      "[&>option]:bg-background",
      "[&>option]:text-muted-foreground",
    );
  });
});
