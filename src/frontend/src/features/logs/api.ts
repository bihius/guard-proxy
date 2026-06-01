import { apiRequest } from "@/lib/api-client";

import type { LogListResponse } from "./types";

type LogTotalParams = {
  action?: string;
  severity?: string;
};

export function fetchLogTotal(
  token: string,
  params: LogTotalParams,
  signal?: AbortSignal
): Promise<number> {
  const query = new URLSearchParams({ page_size: "1" });
  if (params.action) query.set("action", params.action);
  if (params.severity) query.set("severity", params.severity);

  return apiRequest<LogListResponse>(`/logs?${query.toString()}`, {
    token,
    signal,
  }).then((res) => res.total);
}
