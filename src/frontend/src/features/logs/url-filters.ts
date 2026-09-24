import type { LogFilters } from "./types";
import { EMPTY_FILTERS } from "./types";

const URL_FILTER_KEYS = [
  "action",
  "severity",
  "source_ip",
  "vhost",
  "rule_id",
  "date_from",
  "date_to",
] as const;

// Same local "YYYY-MM-DDTHH:mm" shape the date range picker produces.
const DATETIME_LOCAL_PATTERN = /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}$/;

function pad(value: number) {
  return String(value).padStart(2, "0");
}

/** Local-time "YYYY-MM-DDTHH:mm", the format LogFilters date bounds use. */
export function toDateTimeLocal(date: Date): string {
  return [
    date.getFullYear(),
    "-",
    pad(date.getMonth() + 1),
    "-",
    pad(date.getDate()),
    "T",
    pad(date.getHours()),
    ":",
    pad(date.getMinutes()),
  ].join("");
}

/**
 * Seed filters from the query string so other screens can deep-link here —
 * e.g. the dashboard's "top attacking IPs" list opens this page already
 * narrowed to that IP.
 */
export function filtersFromSearchParams(params: URLSearchParams): LogFilters {
  const filters: LogFilters = { ...EMPTY_FILTERS };

  for (const key of URL_FILTER_KEYS) {
    const value = params.get(key);
    if (!value) continue;
    if (key === "rule_id") {
      const parsed = Number(value);
      if (Number.isInteger(parsed) && parsed > 0) filters.rule_id = parsed;
      continue;
    }
    if (key === "action" && !["allow", "deny", "monitor"].includes(value)) continue;
    if ((key === "date_from" || key === "date_to") && !DATETIME_LOCAL_PATTERN.test(value)) {
      continue;
    }
    if (
      key === "severity" &&
      !["info", "warning", "error", "critical"].includes(value)
    ) {
      continue;
    }
    filters[key] = value as never;
  }

  return filters;
}

export function hasAnyFilter(filters: LogFilters): boolean {
  return Object.values(filters).some((value) => value !== "" && value !== null);
}

