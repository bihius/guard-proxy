import { useCallback, useEffect, useRef, useState } from "react";

import { listBannedIps } from "@/features/banned-ips/api";
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
  bannedIps: StatValue;
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
  const { accessToken, hasRole } = useAuth();
  const isAdmin = hasRole("admin");
  const [vhosts, setVHosts] = useState<StatValue>(LOADING);
  const [policies, setPolicies] = useState<StatValue>(LOADING);
  const [blocked, setBlocked] = useState<StatValue>(LOADING);
  const [alerts, setAlerts] = useState<StatValue>(LOADING);
  const [bannedIps, setBannedIps] = useState<StatValue>(LOADING);
  const generationRef = useRef(0);

  const load = useCallback(() => {
    if (!accessToken) return;

    const controller = new AbortController();
    const generation = ++generationRef.current;

    setVHosts(LOADING);
    setPolicies(LOADING);
    setBlocked(LOADING);
    setAlerts(LOADING);
    setBannedIps(LOADING);

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

    // The banned-IPs endpoint is admin-only, so only admins fetch and see this
    // card. Count unique source IPs (an IP can be banned on several vhosts).
    if (isAdmin) {
      listBannedIps(accessToken, controller.signal)
        .then((response) => {
          const uniqueBanned = new Set(
            response.items.filter((item) => item.banned).map((item) => item.ip),
          );
          guard(setBannedIps)(ok(uniqueBanned.size));
        })
        .catch((e) => { if (!isAbortError(e)) guard(setBannedIps)(failed()); });
    }

    return () => controller.abort();
  }, [accessToken, isAdmin]);

  useEffect(() => {
    const cleanup = load();
    return cleanup;
  }, [load]);

  const refresh = useCallback(() => { load(); }, [load]);

  return { vhosts, policies, blocked, alerts, bannedIps, refresh };
}
