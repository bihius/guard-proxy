import { useCallback, useEffect, useRef, useState } from "react";

import { listLogs } from "@/features/logs/api";
import type { Log } from "@/features/logs/types";
import { useAuth } from "@/hooks/use-auth";

import { fetchOverview, fetchTimeseries, fetchTop } from "./api";
import type {
  OverviewResponse,
  StatsWindow,
  TimeseriesResponse,
  TopResponse,
} from "./types";

/** How many recent denied requests the activity feed shows. */
export const RECENT_BLOCKS_LIMIT = 8;

/** Background poll interval. Paused while the tab is hidden. */
const REFRESH_INTERVAL_MS = 30_000;

export type Resource<T> = {
  data: T | null;
  isLoading: boolean;
  error: string | null;
};

export type DashboardData = {
  overview: Resource<OverviewResponse>;
  timeseries: Resource<TimeseriesResponse>;
  top: Resource<TopResponse>;
  recentBlocks: Resource<Log[]>;
  lastUpdatedAt: Date | null;
  refresh: () => void;
};

function pending<T>(previous: Resource<T>): Resource<T> {
  // Keep the previous payload visible while refreshing so a 30s poll doesn't
  // flash skeletons over data the user is already reading.
  return { data: previous.data, isLoading: true, error: null };
}

function isAbortError(error: unknown): boolean {
  return error instanceof Error && error.name === "AbortError";
}

function toMessage(error: unknown, fallback: string): string {
  return error instanceof Error ? error.message : fallback;
}

export function useDashboardData(window: StatsWindow): DashboardData {
  const { accessToken } = useAuth();
  const [overview, setOverview] = useState<Resource<OverviewResponse>>({
    data: null,
    isLoading: true,
    error: null,
  });
  const [timeseries, setTimeseries] = useState<Resource<TimeseriesResponse>>({
    data: null,
    isLoading: true,
    error: null,
  });
  const [top, setTop] = useState<Resource<TopResponse>>({
    data: null,
    isLoading: true,
    error: null,
  });
  const [recentBlocks, setRecentBlocks] = useState<Resource<Log[]>>({
    data: null,
    isLoading: true,
    error: null,
  });
  const [lastUpdatedAt, setLastUpdatedAt] = useState<Date | null>(null);
  const generationRef = useRef(0);

  const load = useCallback(() => {
    if (!accessToken) return;

    const controller = new AbortController();
    const generation = ++generationRef.current;
    const isCurrent = () => generation === generationRef.current;

    setOverview(pending);
    setTimeseries(pending);
    setTop(pending);
    setRecentBlocks(pending);

    // Each section resolves independently: an unreachable HAProxy socket must
    // not take the database-backed chart down with it.
    fetchOverview(accessToken, window, controller.signal)
      .then((data) => {
        if (isCurrent()) {
          setOverview({ data, isLoading: false, error: null });
          setLastUpdatedAt(new Date());
        }
      })
      .catch((error: unknown) => {
        if (!isCurrent() || isAbortError(error)) return;
        setOverview({
          data: null,
          isLoading: false,
          error: toMessage(error, "Failed to load metrics"),
        });
      });

    fetchTimeseries(accessToken, window, controller.signal)
      .then((data) => {
        if (isCurrent()) setTimeseries({ data, isLoading: false, error: null });
      })
      .catch((error: unknown) => {
        if (!isCurrent() || isAbortError(error)) return;
        setTimeseries({
          data: null,
          isLoading: false,
          error: toMessage(error, "Failed to load activity"),
        });
      });

    fetchTop(accessToken, window, 5, controller.signal)
      .then((data) => {
        if (isCurrent()) setTop({ data, isLoading: false, error: null });
      })
      .catch((error: unknown) => {
        if (!isCurrent() || isAbortError(error)) return;
        setTop({
          data: null,
          isLoading: false,
          error: toMessage(error, "Failed to load top threats"),
        });
      });

    listLogs(
      accessToken,
      { page: 1, page_size: RECENT_BLOCKS_LIMIT, action: "deny" },
      controller.signal,
    )
      .then((response) => {
        if (isCurrent())
          setRecentBlocks({ data: response.items, isLoading: false, error: null });
      })
      .catch((error: unknown) => {
        if (!isCurrent() || isAbortError(error)) return;
        setRecentBlocks({
          data: null,
          isLoading: false,
          error: toMessage(error, "Failed to load recent blocks"),
        });
      });

    return () => {
      controller.abort();
    };
  }, [accessToken, window]);

  useEffect(() => load(), [load]);

  useEffect(() => {
    if (!accessToken) return;

    const tick = () => {
      // A backgrounded tab has nobody watching it; polling it only burns
      // requests against the API.
      if (document.visibilityState === "visible") load();
    };
    const timer = globalThis.setInterval(tick, REFRESH_INTERVAL_MS);
    document.addEventListener("visibilitychange", tick);

    return () => {
      globalThis.clearInterval(timer);
      document.removeEventListener("visibilitychange", tick);
    };
  }, [accessToken, load]);

  const refresh = useCallback(() => {
    load();
  }, [load]);

  return { overview, timeseries, top, recentBlocks, lastUpdatedAt, refresh };
}
