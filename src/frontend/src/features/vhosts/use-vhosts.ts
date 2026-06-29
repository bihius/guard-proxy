import { useCallback, useEffect, useRef, useState } from "react";

import { useAuth } from "@/hooks/use-auth";

import { listAllPolicies, listVHosts } from "./api";
import type { Policy, VHost } from "./types";

const PAGE_SIZE = 50;
type VHostsState = {
  vhosts: VHost[];
  total: number;
  page: number;
  pageSize: number;
  searchQuery: string;
  policies: Policy[];
  policyNameById: Record<number, string>;
  isLoading: boolean;
  error: string | null;
  setPage: (page: number) => void;
  setSearchQuery: (query: string) => void;
  refresh: () => void;
};

export function useVHosts(): VHostsState {
  const { accessToken } = useAuth();
  const [vhosts, setVHosts] = useState<VHost[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPageState] = useState(1);
  const [searchQuery, setSearchQueryState] = useState("");
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
      listVHosts(
        accessToken,
        { page, per_page: PAGE_SIZE, q: searchQuery.trim() || undefined },
        controller.signal,
      ),
      listAllPolicies(accessToken, controller.signal),
    ])
      .then(([vhostList, policyList]) => {
        if (generation !== refreshCountRef.current) return;
        setVHosts(vhostList.items);
        setTotal(vhostList.total);
        setPolicies(policyList);
        setIsLoading(false);
      })
      .catch((err: unknown) => {
        if (generation !== refreshCountRef.current) return;
        if (err instanceof Error && err.name === "AbortError") return;
        setError(err instanceof Error ? err.message : "Failed to load vhosts");
        setIsLoading(false);
      });

    return () => {
      controller.abort();
    };
  }, [accessToken, page, searchQuery]);

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

  const setSearchQuery = useCallback((query: string) => {
    setPageState(1);
    setSearchQueryState(query);
  }, []);

  const policyNameById: Record<number, string> = {};
  for (const p of policies) {
    policyNameById[p.id] = p.name;
  }

  return {
    vhosts,
    total,
    page,
    pageSize: PAGE_SIZE,
    searchQuery,
    policies,
    policyNameById,
    isLoading,
    error,
    setPage,
    setSearchQuery,
    refresh,
  };
}
