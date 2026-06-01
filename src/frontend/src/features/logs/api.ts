import { apiRequest } from "@/lib/api-client";

import type { LogAction, LogListResponse } from "./types";

export type ListLogsParams = {
  page: number;
  page_size: number;
  vhost?: string;
  action?: LogAction;
  policy_id?: number | null;
  date_from?: string;
  date_to?: string;
};

function toIso(datetimeLocal: string): string | undefined {
  if (!datetimeLocal) return undefined;
  const d = new Date(datetimeLocal);
  return isNaN(d.getTime()) ? undefined : d.toISOString();
}

export function listLogs(token: string, params: ListLogsParams, signal?: AbortSignal) {
  const query = new URLSearchParams();

  const { date_from, date_to, ...rest } = params;

  for (const [key, value] of Object.entries(rest)) {
    if (value === undefined || value === null || value === "") continue;
    query.append(key, String(value));
  }

  const isoFrom = toIso(date_from ?? "");
  const isoTo = toIso(date_to ?? "");
  if (isoFrom) query.append("date_from", isoFrom);
  if (isoTo) query.append("date_to", isoTo);

  return apiRequest<LogListResponse>(`/logs?${query.toString()}`, { token, signal });
}
