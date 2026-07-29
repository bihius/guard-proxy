import { useRef } from "react";

import { cn } from "@/lib/utils";

import { STATS_WINDOWS, type StatsWindow } from "./types";

type TimeRangeTabsProps = {
  value: StatsWindow;
  onChange: (next: StatsWindow) => void;
};

/**
 * Segmented control selecting the window every dashboard section is scoped to.
 *
 * Implemented as a real tablist so arrow keys move between ranges, which is
 * what a keyboard user expects from a segmented control.
 */
export function TimeRangeTabs({ value, onChange }: TimeRangeTabsProps) {
  const containerRef = useRef<HTMLDivElement>(null);

  const focusTab = (index: number) => {
    const tabs = containerRef.current?.querySelectorAll<HTMLButtonElement>(
      "[role='tab']",
    );
    tabs?.[index]?.focus();
  };

  const handleKeyDown = (event: React.KeyboardEvent<HTMLDivElement>) => {
    const current = STATS_WINDOWS.indexOf(value);
    let next: number | null = null;

    if (event.key === "ArrowRight") next = (current + 1) % STATS_WINDOWS.length;
    if (event.key === "ArrowLeft")
      next = (current - 1 + STATS_WINDOWS.length) % STATS_WINDOWS.length;
    if (event.key === "Home") next = 0;
    if (event.key === "End") next = STATS_WINDOWS.length - 1;
    if (next === null) return;

    const target = STATS_WINDOWS[next];
    if (target === undefined) return;

    event.preventDefault();
    onChange(target);
    focusTab(next);
  };

  return (
    <div
      ref={containerRef}
      role="tablist"
      aria-label="Time range"
      onKeyDown={handleKeyDown}
      className="inline-flex items-center gap-0.5 rounded-full border border-border bg-secondary p-0.5"
    >
      {STATS_WINDOWS.map((window) => {
        const isSelected = window === value;
        return (
          <button
            key={window}
            type="button"
            role="tab"
            aria-selected={isSelected}
            tabIndex={isSelected ? 0 : -1}
            onClick={() => onChange(window)}
            className={cn(
              "cursor-pointer rounded-full px-3 py-1.5 text-sm font-medium transition-colors duration-150",
              isSelected
                ? "bg-primary text-primary-foreground"
                : "text-muted-foreground hover:bg-surface-hover hover:text-foreground",
            )}
          >
            {window}
          </button>
        );
      })}
    </div>
  );
}
