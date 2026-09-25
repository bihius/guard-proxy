import { describe, expect, it } from "vitest";

import { formatDateTime } from "./datetime";

describe("formatDateTime", () => {
  it("reads a timezone-less backend timestamp as UTC", () => {
    expect(formatDateTime("2026-07-29T13:35:00")).toBe(formatDateTime("2026-07-29T13:35:00Z"));
    expect(formatDateTime("2026-07-29T13:35:00")).not.toBe(
      new Intl.DateTimeFormat(undefined, { dateStyle: "short", timeStyle: "medium" }).format(
        new Date("2026-07-29T13:35:00"),
      ),
    );
  });

  it("keeps an explicit offset", () => {
    expect(formatDateTime("2026-07-29T15:35:00+02:00")).toBe(
      formatDateTime("2026-07-29T13:35:00Z"),
    );
  });

  it("returns a placeholder for an unparseable value", () => {
    expect(formatDateTime("not-a-date")).toBe("—");
  });
});
