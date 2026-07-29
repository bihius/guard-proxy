import type { ReactNode } from "react";

import { cn } from "@/lib/utils";

import { describeDelta, formatCount, type DeltaMeaning } from "./format";
import type { MetricValue } from "./types";

type MetricTileProps = {
  label: string;
  metric: MetricValue | null;
  /** Free-form value for counters that have no previous-window comparison. */
  value?: number | null;
  hint?: string;
  icon?: ReactNode;
  tone?: "neutral" | "success" | "warning" | "error" | "info";
  deltaMeaning?: DeltaMeaning;
  isLoading?: boolean;
};

const toneClassMap = {
  neutral: "bg-muted text-muted-foreground",
  success: "bg-success/10 text-success",
  warning: "bg-warning/10 text-warning",
  error: "bg-destructive/10 text-destructive",
  info: "bg-info/10 text-info",
} as const;

export function MetricTile({
  label,
  metric,
  value,
  hint,
  icon,
  tone = "neutral",
  deltaMeaning = "neutral",
  isLoading = false,
}: MetricTileProps) {
  const shown = metric ? metric.current : value;
  const delta = metric ? describeDelta(metric, deltaMeaning) : null;

  return (
    <div className="flex flex-col gap-2 rounded-lg border border-border-subtle bg-surface-raised/40 p-4">
      <div className="flex items-start justify-between gap-2">
        <p className="text-xs font-medium tracking-wide text-muted-foreground uppercase">
          {label}
        </p>
        {icon ? (
          <span
            aria-hidden="true"
            className={cn(
              "flex h-7 w-7 shrink-0 items-center justify-center rounded-md",
              toneClassMap[tone],
            )}
          >
            {icon}
          </span>
        ) : null}
      </div>

      {isLoading ? (
        <div
          className="h-8 w-20 animate-pulse rounded-md bg-muted"
          role="status"
          aria-label="Loading"
        />
      ) : (
        <p className="tabular-figures font-mono text-3xl leading-none font-semibold text-foreground">
          {shown == null ? "—" : formatCount(shown)}
        </p>
      )}

      {!isLoading && delta ? (
        <p className={cn("flex items-center gap-1 text-xs font-medium", delta.className)}>
          {/* Direction is carried by the glyph and the wording, not by colour
              alone — the tile still reads correctly in greyscale. */}
          <span aria-hidden="true">{delta.symbol}</span>
          <span aria-hidden="true">{delta.text}</span>
          <span className="sr-only">{delta.srText}</span>
        </p>
      ) : null}

      {!isLoading && !delta && hint ? (
        <p className="text-xs text-muted-foreground">{hint}</p>
      ) : null}
    </div>
  );
}
