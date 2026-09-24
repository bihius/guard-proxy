import type { ReactNode } from "react";

import { cn } from "@/lib/utils";

export type TopListItem = {
  /** Stable key — usually the rule id, IP or domain. */
  id: string;
  label: string;
  /** Secondary line, e.g. the rule message. */
  caption?: string | null;
  count: number;
  badge?: ReactNode;
  onSelect?: () => void;
};

type TopListProps = {
  items: TopListItem[];
  /** Accessible name for the bar column, e.g. "denied requests". */
  unitLabel: string;
};

/**
 * Ranked horizontal bars. Bar width is relative to the top entry, so the list
 * shows proportion at a glance while the exact number stays readable as text —
 * the bar is never the only way to read a value.
 */
export function TopList({ items, unitLabel }: TopListProps) {
  const peak = Math.max(1, ...items.map((item) => item.count));

  return (
    <ol className="divide-y divide-border-subtle">
      {items.map((item) => {
        const percentage = Math.round((item.count / peak) * 100);
        const content = (
          <>
            <div className="flex items-baseline justify-between gap-3">
              <span className="truncate font-mono text-sm text-foreground">
                {item.label}
              </span>
              <span className="tabular-figures shrink-0 font-mono text-sm font-semibold text-foreground">
                {item.count}
              </span>
            </div>
            {item.caption ? (
              <p className="mt-0.5 truncate text-xs text-muted-foreground">
                {item.caption}
              </p>
            ) : null}
            <div
              className="mt-2 h-1.5 overflow-hidden rounded-full bg-muted"
              role="meter"
              aria-valuenow={item.count}
              aria-valuemin={0}
              aria-valuemax={peak}
              aria-label={`${item.label}: ${item.count} ${unitLabel}`}
            >
              <div
                className="h-full rounded-full bg-destructive/70 transition-[width] duration-300"
                style={{ width: `${percentage}%` }}
              />
            </div>
          </>
        );

        return (
          <li key={item.id} className="py-3 first:pt-0 last:pb-0">
            <div className="flex items-start gap-2">
              <div className="min-w-0 flex-1">
                {item.onSelect ? (
                  <button
                    type="button"
                    onClick={item.onSelect}
                    className={cn(
                      "w-full cursor-pointer rounded-sm text-left transition-opacity duration-150",
                      "hover:opacity-80 focus-visible:opacity-80",
                    )}
                  >
                    {content}
                  </button>
                ) : (
                  content
                )}
              </div>
              {item.badge ? <div className="shrink-0 pt-0.5">{item.badge}</div> : null}
            </div>
          </li>
        );
      })}
    </ol>
  );
}
