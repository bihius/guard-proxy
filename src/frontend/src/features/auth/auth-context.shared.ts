import { createContext } from "react";

import type { AuthContextValue } from "./auth-context.types";

export const AuthContext = createContext<AuthContextValue | null>(null);
