import { createContext } from "react";

export type ConfigChangedContextValue = {
  /** Call after any successful policy/vhost/rule create/update/delete. */
  notifyConfigChanged: () => void;
  /** Registers a listener invoked on every notifyConfigChanged() call; returns an unsubscribe function. */
  subscribe: (listener: () => void) => () => void;
};

export const ConfigChangedContext =
  createContext<ConfigChangedContextValue | null>(null);
