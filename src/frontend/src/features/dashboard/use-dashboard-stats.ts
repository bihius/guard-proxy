import { useCallback, useEffect, useRef, useState } from "react";

import { listPolicies, listVHosts } from "@/features/vhosts/api";
import { fetchLogTotal } from "@/features/logs/api";
import { useAuth } from "@/hooks/use-auth";

type StatValue = {
  count: number | null;
  error: boolean;
};

type DashboardStatsState = {
  vhosts: StatValue;
  policies: StatValue;
  blocked: StatValue;
  alerts: StatValue;
  isLoading: boolean;
  refresh: () => void;
};

const INITIAL_STAT: StatValue = { count: null, error: false };

export function useDashboardStats(): DashboardStatsState {
  const { accessToken } = useAuth();
  const [vhosts, setVHosts] = useState<StatValue>(INITIAL_STAT);
  const [policies, setPolicies] = useState<StatValue>(INITIAL_STAT);
  const [blocked, setBlocked] = useState<StatValue>(INITIAL_STAT);
  const [alerts, setAlerts] = useState<StatValue>(INITIAL_STAT);
  const [isLoading, setIsLoading] = useState(true);
  const refreshCountRef = useRef(0);

  const load = useCallback(() => {
    if (!accessToken) return;

    const controller = new AbortController();
    const generation = ++refreshCountRef.current;

    setIsLoading(true);

    Promise.allSettled([
      listVHosts(accessToken, controller.signal),
      listPolicies(accessToken, controller.signal),
      fetchLogTotal(accessToken, { action: "deny" }, controller.signal),
      fetchLogTotal(accessToken, { severity: "critical" }, controller.signal),
    ]).then(([vhostResult, policyResult, blockedResult, alertsResult]) => {
      if (generation !== refreshCountRef.current) return;

      setVHosts(
        vhostResult.status === "fulfilled"
          ? { count: vhostResult.value.length, error: false }
          : { count: null, error: true }
      );
      setPolicies(
        policyResult.status === "fulfilled"
          ? { count: policyResult.value.length, error: false }
          : { count: null, error: true }
      );
      setBlocked(
        blockedResult.status === "fulfilled"
          ? { count: blockedResult.value, error: false }
          : { count: null, error: true }
      );
      setAlerts(
        alertsResult.status === "fulfilled"
          ? { count: alertsResult.value, error: false }
          : { count: null, error: true }
      );

      setIsLoading(false);
    });

    return () => {
      controller.abort();
    };
  }, [accessToken]);

  useEffect(() => {
    const cleanup = load();
    return cleanup;
  }, [load]);

  const refresh = useCallback(() => {
    load();
  }, [load]);

  return { vhosts, policies, blocked, alerts, isLoading, refresh };
}
