import { useCallback, useEffect, useRef, useState } from "react";

import { listVHosts } from "@/features/vhosts/api";
import { useAuth } from "@/hooks/use-auth";

import { listPolicies } from "./api";
import type { Policy } from "./types";

type PoliciesState = {
  policies: Policy[];
  assignedPolicyIds: Set<number>;
  isLoading: boolean;
  error: string | null;
  refresh: () => void;
};

export function usePolicies(): PoliciesState {
  const { accessToken } = useAuth();
  const [policies, setPolicies] = useState<Policy[]>([]);
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
      listPolicies(accessToken, controller.signal),
      listVHosts(accessToken, controller.signal),
    ])
      .then(([policyList, vhostList]) => {
        if (generation !== refreshCountRef.current) return;
        setPolicies(policyList);
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
  }, [accessToken]);

  useEffect(() => {
    const cleanup = fetch();
    return cleanup;
  }, [fetch]);

  const refresh = useCallback(() => {
    fetch();
  }, [fetch]);

  return { policies, assignedPolicyIds, isLoading, error, refresh };
}
