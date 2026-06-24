import { useCallback, useEffect, useRef, useState } from "react";

import { useAuth } from "@/hooks/use-auth";
import { listPolicies } from "@/features/vhosts/api";
import type { Policy } from "@/features/vhosts/types";

import { listLogs } from "./api";
import type { Log, LogFilters } from "./types";
import { EMPTY_FILTERS } from "./types";

const PAGE_SIZE = 50;

type LogsState = {
  logs: Log[];
  total: number;
  page: number;
  pageSize: number;
  policies: Policy[];
  policyNameById: Record<number, string>;
  isLoading: boolean;
  error: string | null;
  setPage: (page: number) => void;
  applyFilters: (filters: LogFilters) => void;
  refresh: () => void;
};

export function useLogs(): LogsState {
  const { accessToken } = useAuth();
  const [logs, setLogs] = useState<Log[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPageState] = useState(1);
  const [applied, setApplied] = useState<LogFilters>(EMPTY_FILTERS);
  const [policies, setPolicies] = useState<Policy[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const refreshCountRef = useRef(0);

  const fetch = useCallback(() => {
    if (!accessToken) return;

    const controller = new AbortController();
    const generation = ++refreshCountRef.current;

    setIsLoading(true);
    setError(null);

    Promise.all([
      listLogs(
        accessToken,
        {
          page,
          page_size: PAGE_SIZE,
          vhost: applied.vhost || undefined,
          action: applied.action !== "" ? applied.action : undefined,
          policy_id: applied.policy_id ?? undefined,
          date_from: applied.date_from || undefined,
          date_to: applied.date_to || undefined,
          severity: applied.severity !== "" ? applied.severity : undefined,
          source_ip: applied.source_ip || undefined,
          method: applied.method || undefined,
          rule_id: applied.rule_id ?? undefined,
          min_score: applied.min_score ?? undefined,
        },
        controller.signal,
      ),
      listPolicies(accessToken, controller.signal),
    ])
      .then(([logList, policyList]) => {
        if (generation !== refreshCountRef.current) return;
        setLogs(logList.items);
        setTotal(logList.total);
        setPolicies(policyList);
        setIsLoading(false);
      })
      .catch((err: unknown) => {
        if (generation !== refreshCountRef.current) return;
        if (err instanceof Error && err.name === "AbortError") return;
        setError(err instanceof Error ? err.message : "Failed to load logs");
        setIsLoading(false);
      });

    return () => {
      controller.abort();
    };
  }, [accessToken, page, applied]);

  useEffect(() => {
    const cleanup = fetch();
    return cleanup;
  }, [fetch]);

  const refresh = useCallback(() => {
    fetch();
  }, [fetch]);

  const setPage = useCallback((nextPage: number) => {
    setPageState(nextPage);
  }, []);

  const applyFilters = useCallback((filters: LogFilters) => {
    setPageState(1);
    setApplied(filters);
  }, []);

  const policyNameById: Record<number, string> = {};
  for (const p of policies) {
    policyNameById[p.id] = p.name;
  }

  return {
    logs,
    total,
    page,
    pageSize: PAGE_SIZE,
    policies,
    policyNameById,
    isLoading,
    error,
    setPage,
    applyFilters,
    refresh,
  };
}
