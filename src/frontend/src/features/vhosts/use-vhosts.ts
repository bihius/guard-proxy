import { useCallback, useEffect, useRef, useState } from "react";

import { useAuth } from "@/hooks/use-auth";

import { listPolicies, listVHosts } from "./api";
import type { Policy, VHost } from "./types";

type VHostsState = {
  vhosts: VHost[];
  policies: Policy[];
  policyNameById: Record<number, string>;
  isLoading: boolean;
  error: string | null;
  refresh: () => void;
};

export function useVHosts(): VHostsState {
  const { accessToken } = useAuth();
  const [vhosts, setVHosts] = useState<VHost[]>([]);
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
      listVHosts(accessToken, controller.signal),
      listPolicies(accessToken, controller.signal),
    ])
      .then(([vhostList, policyList]) => {
        if (generation !== refreshCountRef.current) return;
        setVHosts(vhostList);
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
  }, [accessToken]);

  useEffect(() => {
    const cleanup = fetch();
    return cleanup;
  }, [fetch]);

  const refresh = useCallback(() => {
    fetch();
  }, [fetch]);

  const policyNameById: Record<number, string> = {};
  for (const p of policies) {
    policyNameById[p.id] = p.name;
  }

  return { vhosts, policies, policyNameById, isLoading, error, refresh };
}
