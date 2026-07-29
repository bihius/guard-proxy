import { useState } from "react";

import { cn } from "@/lib/utils";

import { formatBucketLabel } from "./format";
import type { TimeseriesBucket } from "./types";

/**
 * Stacked bar chart of allow / monitor / deny counts per time bucket.
 *
 * Hand-rolled SVG rather than a charting dependency: the shape is simple, and
 * drawing it directly keeps every colour on the app's semantic tokens so both
 * themes work without a parallel styling system.
 *
 * The chart is scaled entirely through `viewBox`, so it resizes with its
 * container without measuring the DOM.
 */

const VIEWBOX_HEIGHT = 100;
const BAR_GAP_RATIO = 0.28;

/**
 * Bottom-to-top stacking order: routine traffic first, blocks on top.
 *
 * Both class names are spelled out in full because Tailwind extracts classes
 * by scanning source text — deriving `bg-*` from `fill-*` at runtime would
 * compile to nothing.
 */
const SERIES = [
  {
    key: "allow",
    label: "Allowed",
    fillClass: "fill-chart-allow",
    dotClass: "bg-chart-allow",
  },
  {
    key: "monitor",
    label: "Monitored",
    fillClass: "fill-chart-monitor",
    dotClass: "bg-chart-monitor",
  },
  {
    key: "deny",
    label: "Blocked",
    fillClass: "fill-chart-deny",
    dotClass: "bg-chart-deny",
  },
] as const;

type SeriesKey = (typeof SERIES)[number]["key"];

type ActivityChartProps = {
  buckets: TimeseriesBucket[];
  bucketSeconds: number;
};

function bucketTotal(bucket: TimeseriesBucket): number {
  return bucket.allow + bucket.monitor + bucket.deny;
}

export function ActivityChart({ buckets, bucketSeconds }: ActivityChartProps) {
  const [hovered, setHovered] = useState<number | null>(null);

  const totals = buckets.map(bucketTotal);
  // A flat all-zero series would divide by zero; 1 keeps every bar at height 0.
  const peak = Math.max(1, ...totals);
  const slotWidth = 100 / Math.max(1, buckets.length);
  const barWidth = slotWidth * (1 - BAR_GAP_RATIO);

  const summary = `Request activity across ${buckets.length} intervals: ${totals.reduce(
    (sum, value) => sum + value,
    0,
  )} requests total, ${buckets.reduce((sum, b) => sum + b.deny, 0)} blocked.`;

  const active = hovered === null ? null : buckets[hovered];

  return (
    <div className="relative">
      <svg
        viewBox={`0 0 100 ${VIEWBOX_HEIGHT}`}
        preserveAspectRatio="none"
        role="img"
        aria-label={summary}
        className="h-40 w-full sm:h-52"
        onMouseLeave={() => setHovered(null)}
      >
        <title>Request activity over time</title>
        <desc>{summary}</desc>

        {[0.25, 0.5, 0.75].map((fraction) => (
          <line
            key={fraction}
            x1="0"
            x2="100"
            y1={VIEWBOX_HEIGHT * fraction}
            y2={VIEWBOX_HEIGHT * fraction}
            className="stroke-chart-grid"
            strokeWidth="0.3"
            vectorEffect="non-scaling-stroke"
          />
        ))}

        {buckets.map((bucket, index) => {
          const x = index * slotWidth + (slotWidth - barWidth) / 2;
          let offset = 0;

          return (
            <g
              key={bucket.bucket_at}
              onMouseEnter={() => setHovered(index)}
              onFocus={() => setHovered(index)}
            >
              {/* Full-height hit area: hovering a near-empty bucket should still
                  reveal its tooltip. */}
              <rect
                x={index * slotWidth}
                y={0}
                width={slotWidth}
                height={VIEWBOX_HEIGHT}
                className={cn(
                  "fill-foreground/0 transition-[fill] duration-150",
                  hovered === index && "fill-foreground/5",
                )}
              />
              {SERIES.map((series) => {
                const value = bucket[series.key as SeriesKey];
                if (value === 0) return null;
                const height = (value / peak) * VIEWBOX_HEIGHT;
                const y = VIEWBOX_HEIGHT - offset - height;
                offset += height;
                return (
                  <rect
                    key={series.key}
                    x={x}
                    y={y}
                    width={barWidth}
                    height={height}
                    className={cn(series.fillClass, "animate-chart-bar")}
                    style={{ animationDelay: `${Math.min(index * 12, 300)}ms` }}
                  />
                );
              })}
            </g>
          );
        })}
      </svg>

      {active ? (
        <div
          className="pointer-events-none absolute -top-1 z-10 w-max -translate-x-1/2 rounded-md border border-border bg-card px-2.5 py-1.5 text-xs shadow-lg"
          style={{
            left: `${Math.min(90, Math.max(10, ((hovered ?? 0) + 0.5) * slotWidth))}%`,
          }}
        >
          <p className="font-medium text-foreground">
            {formatBucketLabel(active.bucket_at, bucketSeconds)}
          </p>
          <dl className="mt-1 space-y-0.5">
            {SERIES.map((series) => (
              <div key={series.key} className="flex items-center gap-2">
                <span
                  aria-hidden="true"
                  className={cn("h-2 w-2 rounded-full", series.dotClass)}
                />
                <dt className="text-muted-foreground">{series.label}</dt>
                <dd className="tabular-figures ml-auto font-mono text-foreground">
                  {active[series.key as SeriesKey]}
                </dd>
              </div>
            ))}
          </dl>
        </div>
      ) : null}

      <div className="mt-2 flex justify-between text-xs text-muted-foreground">
        <span>{formatBucketLabel(buckets[0]?.bucket_at ?? "", bucketSeconds)}</span>
        <span>
          {formatBucketLabel(buckets[buckets.length - 1]?.bucket_at ?? "", bucketSeconds)}
        </span>
      </div>

      {/* Screen-reader and colour-blind fallback: the same numbers as a table,
          so nothing in this chart is conveyed by colour alone. */}
      <table className="sr-only">
        <caption>Request activity per interval</caption>
        <thead>
          <tr>
            <th scope="col">Interval</th>
            {SERIES.map((series) => (
              <th key={series.key} scope="col">
                {series.label}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {buckets.map((bucket) => (
            <tr key={bucket.bucket_at}>
              <th scope="row">{formatBucketLabel(bucket.bucket_at, bucketSeconds)}</th>
              {SERIES.map((series) => (
                <td key={series.key}>{bucket[series.key as SeriesKey]}</td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function ActivityChartLegend() {
  return (
    <ul className="flex flex-wrap items-center gap-4 text-xs text-muted-foreground">
      {SERIES.map((series) => (
        <li key={series.key} className="flex items-center gap-1.5">
          <span
            aria-hidden="true"
            className={cn("h-2.5 w-2.5 rounded-[2px]", series.dotClass)}
          />
          {series.label}
        </li>
      ))}
    </ul>
  );
}
