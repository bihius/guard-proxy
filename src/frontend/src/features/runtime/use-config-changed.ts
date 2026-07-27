import { useContext } from "react";

import {
  ConfigChangedContext,
  type ConfigChangedContextValue,
} from "./config-changed-context";

export function useConfigChanged(): ConfigChangedContextValue {
  const context = useContext(ConfigChangedContext);
  if (!context) {
    throw new Error(
      "useConfigChanged must be used within a ConfigChangedProvider",
    );
  }
  return context;
}
