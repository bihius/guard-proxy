import { apiRequest } from "@/lib/api-client";

import type {
  OverviewResponse,
  StatsWindow,
  TimeseriesResponse,
  TopResponse,
} from "./types";

export function fetchOverview(
  token: string,
  window: StatsWindow,
  signal?: AbortSignal,
): Promise<OverviewResponse> {
  return apiRequest<OverviewResponse>(`/stats/overview?window=${window}`, {
    token,
    signal,
  });
}

export function fetchTimeseries(
  token: string,
  window: StatsWindow,
  signal?: AbortSignal,
): Promise<TimeseriesResponse> {
  return apiRequest<TimeseriesResponse>(`/stats/timeseries?window=${window}`, {
    token,
    signal,
  });
}

export function fetchTop(
  token: string,
  window: StatsWindow,
  limit = 5,
  signal?: AbortSignal,
): Promise<TopResponse> {
  return apiRequest<TopResponse>(`/stats/top?window=${window}&limit=${limit}`, {
    token,
    signal,
  });
}
