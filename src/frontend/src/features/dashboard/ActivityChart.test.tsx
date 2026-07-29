import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { ActivityChart } from "./ActivityChart";
import type { TimeseriesBucket } from "./types";

const buckets: TimeseriesBucket[] = [
  { bucket_at: "2026-07-29T10:00:00Z", allow: 50, deny: 50, monitor: 0 },
  { bucket_at: "2026-07-29T11:00:00Z", allow: 0, deny: 0, monitor: 0 },
];

function renderChart(data: TimeseriesBucket[] = buckets) {
  return render(<ActivityChart buckets={data} bucketSeconds={3600} />);
}

describe("ActivityChart", () => {
  it("scales bar heights against the busiest bucket", () => {
    const { container } = renderChart();
    // The 100-unit viewBox splits evenly between two equal series.
    const bars = container.querySelectorAll("rect.animate-chart-bar");

    expect(bars).toHaveLength(2);
    expect(bars[0]).toHaveAttribute("height", "50");
    expect(bars[1]).toHaveAttribute("height", "50");
  });

  it("draws no bars for an empty bucket instead of dividing by zero", () => {
    const { container } = renderChart([
      { bucket_at: "2026-07-29T10:00:00Z", allow: 0, deny: 0, monitor: 0 },
    ]);

    expect(container.querySelectorAll("rect.animate-chart-bar")).toHaveLength(0);
  });

  it("describes itself for screen readers", () => {
    renderChart();

    expect(
      screen.getByRole("img", {
        name: /100 requests total, 50 blocked/i,
      }),
    ).toBeInTheDocument();
  });

  it("mirrors every value in a table so colour is never the only channel", () => {
    renderChart();

    const table = screen.getByRole("table", { name: /request activity per interval/i });
    const rows = within(table).getAllByRole("row");

    expect(rows).toHaveLength(3); // header + 2 buckets
    expect(within(rows[1]!).getAllByRole("cell").map((c) => c.textContent)).toEqual([
      "50",
      "0",
      "50",
    ]);
  });
});
