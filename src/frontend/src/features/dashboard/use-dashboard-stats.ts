import { useCallback, useEffect, useRef, useState } from "react";

import { fetchLogTotal } from "@/features/logs/api";
import type { LogAction, LogSeverity } from "@/features/logs/types";
import { listAllVHosts } from "@/features/vhosts/api";
import { listAllPolicies } from "@/features/policies/api";
import { useAuth } from "@/hooks/use-auth";

export type StatValue = {
  count: number | null;
  error: boolean;
  isLoading: boolean;
};

type DashboardStatsState = {
  vhosts: StatValue;
  policies: StatValue;
  blocked: StatValue;
  alerts: StatValue;
  refresh: () => void;
};

const LOADING: StatValue = { count: null, error: false, isLoading: true };

function ok(count: number): StatValue {
  return { count, error: false, isLoading: false };
}

function failed(): StatValue {
  return { count: null, error: true, isLoading: false };
}

function isAbortError(e: unknown): boolean {
  return e instanceof Error && e.name === "AbortError";
}

export function useDashboardStats(): DashboardStatsState {
  const { accessToken } = useAuth();
  const [vhosts, setVHosts] = useState<StatValue>(LOADING);
  const [policies, setPolicies] = useState<StatValue>(LOADING);
  const [blocked, setBlocked] = useState<StatValue>(LOADING);
  const [alerts, setAlerts] = useState<StatValue>(LOADING);
  const generationRef = useRef(0);

  const load = useCallback(() => {
    if (!accessToken) return;

    const controller = new AbortController();
    const generation = ++generationRef.current;

    setVHosts(LOADING);
    setPolicies(LOADING);
    setBlocked(LOADING);
    setAlerts(LOADING);

    // Each card resolves independently so fast cards aren't blocked by slow ones.
    // Aborted fetches are silently dropped (not surfaced as errors).
    const guard =
      (setter: (v: StatValue) => void) => (value: StatValue) => {
        if (generation === generationRef.current) setter(value);
      };

    listAllVHosts(accessToken, controller.signal)
      .then((list) =>
        guard(setVHosts)(
          ok(list.filter((v) => v.is_active && v.policy_id != null).length),
        ),
      )
      .catch((e) => { if (!isAbortError(e)) guard(setVHosts)(failed()); });

    listAllPolicies(accessToken, controller.signal)
      .then((list) =>
        guard(setPolicies)(ok(list.filter((p) => p.is_active).length)),
      )
      .catch((e) => { if (!isAbortError(e)) guard(setPolicies)(failed()); });

    fetchLogTotal(accessToken, { action: "deny" as LogAction }, controller.signal)
      .then((total) => guard(setBlocked)(ok(total)))
      .catch((e) => { if (!isAbortError(e)) guard(setBlocked)(failed()); });

    fetchLogTotal(accessToken, { severity: "critical" as LogSeverity }, controller.signal)
      .then((total) => guard(setAlerts)(ok(total)))
      .catch((e) => { if (!isAbortError(e)) guard(setAlerts)(failed()); });

    return () => controller.abort();
  }, [accessToken]);

  useEffect(() => {
    const cleanup = load();
    return cleanup;
  }, [load]);

  const refresh = useCallback(() => { load(); }, [load]);

  return { vhosts, policies, blocked, alerts, refresh };
}
