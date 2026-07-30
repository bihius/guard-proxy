import { describe, expect, it } from "vitest";

import { describeDelta, formatBucketLabel, formatRelativeTime } from "./format";

describe("describeDelta", () => {
  it("marks a rise in blocked traffic as a warning, a fall as good", () => {
    const up = describeDelta(
      { current: 120, previous: 100, delta_pct: 20 },
      "increase-is-bad",
    );
    const down = describeDelta(
      { current: 80, previous: 100, delta_pct: -20 },
      "increase-is-bad",
    );

    expect(up).toMatchObject({ symbol: "▲", text: "20%", className: "text-warning" });
    expect(down).toMatchObject({ symbol: "▼", text: "20%", className: "text-success" });
  });

  it("stays neutral when direction carries no judgement", () => {
    const result = describeDelta(
      { current: 120, previous: 100, delta_pct: 20 },
      "neutral",
    );

    expect(result?.className).toBe("text-muted-foreground");
  });

  it("reports 'new' instead of an infinite percentage", () => {
    const result = describeDelta(
      { current: 5, previous: 0, delta_pct: null },
      "increase-is-bad",
    );

    expect(result?.text).toBe("new");
  });

  it("renders nothing when both windows are empty", () => {
    expect(describeDelta({ current: 0, previous: 0, delta_pct: null }, "neutral")).toBeNull();
  });

  it("says 'no change' rather than showing 0%", () => {
    const result = describeDelta(
      { current: 100, previous: 100, delta_pct: 0 },
      "increase-is-bad",
    );

    expect(result).toMatchObject({ symbol: "▬", text: "no change" });
  });

  it("always pairs colour with a glyph and screen-reader wording", () => {
    const result = describeDelta(
      { current: 120, previous: 100, delta_pct: 20 },
      "increase-is-bad",
    );

    expect(result?.symbol).not.toBe("");
    expect(result?.srText).toMatch(/up 20 percent/);
  });
});

describe("formatBucketLabel", () => {
  it("falls back to a date for day-sized buckets", () => {
    expect(formatBucketLabel("2026-07-29T00:00:00Z", 86_400)).not.toMatch(/:/);
  });

  it("uses a clock time for sub-hour buckets", () => {
    expect(formatBucketLabel("2026-07-29T13:35:00Z", 300)).toMatch(/\d/);
  });

  it("degrades gracefully on an unparsable timestamp", () => {
    expect(formatBucketLabel("not-a-date", 3600)).toBe("—");
  });
});

describe("formatRelativeTime", () => {
  const now = new Date("2026-07-29T12:00:00Z");

  it("collapses anything under a minute to 'just now'", () => {
    expect(formatRelativeTime("2026-07-29T11:59:30Z", now)).toBe("just now");
  });

  it("scales up through minutes, hours and days", () => {
    expect(formatRelativeTime("2026-07-29T11:30:00Z", now)).toMatch(/30 minutes/);
    expect(formatRelativeTime("2026-07-29T09:00:00Z", now)).toMatch(/3 hours/);
    expect(formatRelativeTime("2026-07-27T12:00:00Z", now)).toMatch(/2 days|day before/);
  });

  it("degrades gracefully on an unparsable timestamp", () => {
    expect(formatRelativeTime("nope", now)).toBe("—");
  });
});
