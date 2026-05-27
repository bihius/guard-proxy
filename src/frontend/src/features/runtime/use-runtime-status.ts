import { useCallback, useEffect, useRef, useState } from "react";

import { useAuth } from "@/hooks/use-auth";

import { getRuntimeStatus } from "./api";
import type { RuntimeStatusResponse } from "./types";

type RuntimeStatusState = {
  data: RuntimeStatusResponse | null;
  isLoading: boolean;
  error: string | null;
  refresh: () => void;
};

export function useRuntimeStatus(): RuntimeStatusState {
  const { accessToken } = useAuth();
  const [data, setData] = useState<RuntimeStatusResponse | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const refreshCountRef = useRef(0);

  const fetch = useCallback(() => {
    if (!accessToken) return;

    const controller = new AbortController();
    const generation = ++refreshCountRef.current;

    setIsLoading(true);
    setError(null);

    getRuntimeStatus(accessToken, controller.signal)
      .then((result) => {
        if (generation === refreshCountRef.current) {
          setData(result);
          setIsLoading(false);
        }
      })
      .catch((err: unknown) => {
        if (generation !== refreshCountRef.current) return;
        if (
          err instanceof Error &&
          (err.name === "AbortError" ||
            (err as { name?: string }).name === "AbortError")
        ) {
          return;
        }
        setError(err instanceof Error ? err.message : "Failed to load status");
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

  return { data, isLoading, error, refresh };
}
