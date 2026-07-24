import { useCallback, useRef, type PropsWithChildren } from "react";

import { ConfigChangedContext } from "./config-changed-context";

/**
 * Bridges policy/vhost/rule mutation success handlers (deep in the page
 * tree) to the navbar's runtime-status poll (also deep in the page tree,
 * as a sibling) without lifting `useRuntimeStatus` state up — any consumer
 * can subscribe, any consumer can notify.
 */
export function ConfigChangedProvider({ children }: PropsWithChildren) {
  const listenersRef = useRef(new Set<() => void>());

  const subscribe = useCallback((listener: () => void) => {
    listenersRef.current.add(listener);
    return () => {
      listenersRef.current.delete(listener);
    };
  }, []);

  const notifyConfigChanged = useCallback(() => {
    listenersRef.current.forEach((listener) => listener());
  }, []);

  return (
    <ConfigChangedContext.Provider value={{ notifyConfigChanged, subscribe }}>
      {children}
    </ConfigChangedContext.Provider>
  );
}
