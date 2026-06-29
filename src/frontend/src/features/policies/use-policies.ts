import { useCallback, useEffect, useRef, useState } from "react";

import { listAllVHosts } from "@/features/vhosts/api";
import { useAuth } from "@/hooks/use-auth";

import { listPolicies } from "./api";
import type { Policy } from "./types";

const PAGE_SIZE = 50;
type PoliciesState = {
  policies: Policy[];
  total: number;
  page: number;
  pageSize: number;
  searchQuery: string;
  assignedPolicyIds: Set<number>;
  isLoading: boolean;
  error: string | null;
  setPage: (page: number) => void;
  setSearchQuery: (query: string) => void;
  refresh: () => void;
};

export function usePolicies(): PoliciesState {
  const { accessToken } = useAuth();
  const [policies, setPolicies] = useState<Policy[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPageState] = useState(1);
  const [searchQuery, setSearchQueryState] = useState("");
  const [assignedPolicyIds, setAssignedPolicyIds] = useState<Set<number>>(new Set());
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
      listPolicies(
        accessToken,
        { page, per_page: PAGE_SIZE, q: searchQuery.trim() || undefined },
        controller.signal,
      ),
      listAllVHosts(accessToken, controller.signal),
    ])
      .then(([policyList, vhostList]) => {
        if (generation !== refreshCountRef.current) return;
        setPolicies(policyList.items);
        setTotal(policyList.total);
        const ids = new Set(
          vhostList
            .map((v) => v.policy_id)
            .filter((id): id is number => id != null),
        );
        setAssignedPolicyIds(ids);
        setIsLoading(false);
      })
      .catch((err: unknown) => {
        if (generation !== refreshCountRef.current) return;
        if (err instanceof Error && err.name === "AbortError") return;
        setError(err instanceof Error ? err.message : "Failed to load policies");
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

  return {
    policies,
    total,
    page,
    pageSize: PAGE_SIZE,
    searchQuery,
    assignedPolicyIds,
    isLoading,
    error,
    setPage,
    setSearchQuery,
    refresh,
  };
}
