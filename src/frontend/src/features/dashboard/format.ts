import type { MetricValue } from "./types";

/**
 * Whether a rising number is good news. Blocked requests going up is a
 * warning; the same shape of change on allowed traffic means nothing.
 */
export type DeltaMeaning = "increase-is-bad" | "increase-is-good" | "neutral";

export type DeltaDisplay = {
  symbol: string;
  text: string;
  srText: string;
  className: string;
};

export function formatCount(value: number): string {
  return new Intl.NumberFormat("en-US").format(value);
}

/** Bucket labels drop to a date once buckets span a day or more. */
export function formatBucketLabel(iso: string, bucketSeconds: number): string {
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return "—";
  if (bucketSeconds >= 86_400) {
    return date.toLocaleDateString(undefined, { month: "short", day: "numeric" });
  }
  if (bucketSeconds >= 21_600) {
    return date.toLocaleString(undefined, {
      month: "short",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  }
  return date.toLocaleTimeString(undefined, { hour: "2-digit", minute: "2-digit" });
}

/** "4 minutes ago" reads faster than a timestamp when scanning for freshness. */
export function formatRelativeTime(iso: string, now: Date = new Date()): string {
  const target = new Date(iso);
  if (Number.isNaN(target.getTime())) return "—";

  const seconds = Math.round((now.getTime() - target.getTime()) / 1000);
  if (seconds < 60) return "just now";

  const formatter = new Intl.RelativeTimeFormat(undefined, { numeric: "auto" });
  const units: [Intl.RelativeTimeFormatUnit, number][] = [
    ["year", 31_536_000],
    ["month", 2_592_000],
    ["day", 86_400],
    ["hour", 3_600],
    ["minute", 60],
  ];
  for (const [unit, size] of units) {
    if (seconds >= size) return formatter.format(-Math.floor(seconds / size), unit);
  }
  return "just now";
}

/**
 * Turn a window-over-window comparison into something renderable.
 *
 * Direction is always carried by a glyph and by wording, never by colour
 * alone, so the tile still reads correctly in greyscale.
 */
export function describeDelta(
  metric: MetricValue,
  meaning: DeltaMeaning,
): DeltaDisplay | null {
  if (metric.delta_pct === null) {
    // No baseline: "+∞%" is meaningless, so say what actually happened.
    if (metric.current === 0) return null;
    return {
      symbol: "▲",
      text: "new",
      srText: "new activity, nothing in the previous period",
      className:
        meaning === "increase-is-bad" ? "text-warning" : "text-muted-foreground",
    };
  }

  const magnitude = Math.abs(metric.delta_pct);
  if (magnitude === 0) {
    return {
      symbol: "▬",
      text: "no change",
      srText: "unchanged from the previous period",
      className: "text-muted-foreground",
    };
  }

  const isUp = metric.delta_pct > 0;
  const isGood =
    meaning === "neutral" ? null : isUp === (meaning === "increase-is-good");

  return {
    symbol: isUp ? "▲" : "▼",
    text: `${magnitude}%`,
    srText: `${isUp ? "up" : "down"} ${magnitude} percent from the previous period`,
    className:
      isGood === null
        ? "text-muted-foreground"
        : isGood
          ? "text-success"
          : "text-warning",
  };
}
