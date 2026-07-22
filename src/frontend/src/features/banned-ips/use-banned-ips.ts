import { useCallback, useEffect, useRef, useState } from "react";

import { useAuth } from "@/hooks/use-auth";

import { listBannedIps } from "./api";
import type { BannedIp } from "./types";

const PAGE_SIZE = 50;

type BannedIpsState = {
  items: BannedIp[];
  total: number;
  page: number;
  pageSize: number;
  searchQuery: string;
  isLoading: boolean;
  error: string | null;
  setPage: (page: number) => void;
  setSearchQuery: (query: string) => void;
  refresh: () => void;
};

export function useBannedIps(): BannedIpsState {
  const { accessToken } = useAuth();
  const [bannedIps, setBannedIps] = useState<BannedIp[]>([]);
  const [page, setPageState] = useState(1);
  const [searchQuery, setSearchQueryState] = useState("");
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const refreshCountRef = useRef(0);

  const fetch = useCallback(() => {
    if (!accessToken) return;

    const controller = new AbortController();
    const generation = ++refreshCountRef.current;

    setIsLoading(true);
    setError(null);

    listBannedIps(accessToken, controller.signal)
      .then((response) => {
        if (generation !== refreshCountRef.current) return;
        setBannedIps(response.items.filter((item) => item.banned));
        setIsLoading(false);
      })
      .catch((err: unknown) => {
        if (generation !== refreshCountRef.current) return;
        if (err instanceof Error && err.name === "AbortError") return;
        setError(err instanceof Error ? err.message : "Failed to load banned IPs");
        setIsLoading(false);
      });

    return () => {
      controller.abort();
    };
  }, [accessToken]);

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

  const trimmedQuery = searchQuery.trim().toLowerCase();
  const filtered = trimmedQuery
    ? bannedIps.filter((item) => item.ip.toLowerCase().includes(trimmedQuery))
    : bannedIps;

  const total = filtered.length;
  const start = (page - 1) * PAGE_SIZE;
  const items = filtered.slice(start, start + PAGE_SIZE);

  return {
    items,
    total,
    page,
    pageSize: PAGE_SIZE,
    searchQuery,
    isLoading,
    error,
    setPage,
    setSearchQuery,
    refresh,
  };
}
