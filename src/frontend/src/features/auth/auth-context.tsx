import {
  useCallback,
  useEffect,
  useMemo,
  useState,
  type PropsWithChildren,
} from "react";

import { ApiError } from "@/lib/api-client";
import type { CurrentUser, LoginRequest, UserRole } from "@/types/api";

import { getCurrentUser, login, logout, refreshSession } from "./api";
import { AuthContext } from "./auth-context.shared";
import type { AuthContextValue } from "./auth-context.types";

export function AuthProvider({ children }: PropsWithChildren) {
  const [user, setUser] = useState<CurrentUser | null>(null);
  const [accessToken, setAccessToken] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [loginError, setLoginError] = useState<string | null>(null);

  useEffect(() => {
    let isMounted = true;

    async function restoreSession() {
      try {
        const tokens = await refreshSession();
        const currentUser = await getCurrentUser(tokens.access_token);

        if (!isMounted) {
          return;
        }

        setAccessToken(tokens.access_token);
        setUser(currentUser);
        setLoginError(null);
      } catch {
        if (!isMounted) {
          return;
        }

        setAccessToken(null);
        setUser(null);
        setLoginError(null);
      } finally {
        if (isMounted) {
          setIsLoading(false);
        }
      }
    }

    void restoreSession();

    return () => {
      isMounted = false;
    };
  }, []);

  const signIn = useCallback(async (credentials: LoginRequest) => {
    setLoginError(null);
    let tokens;

    try {
      tokens = await login(credentials);
    } catch (error) {
      if (error instanceof ApiError) {
        setLoginError(error.detail);
      } else {
        setLoginError("Could not sign in");
      }

      throw error;
    }

    setAccessToken(tokens.access_token);

    try {
      const currentUser = await getCurrentUser(tokens.access_token);
      setUser(currentUser);
      setLoginError(null);
    } catch (error) {
      setAccessToken(null);
      setUser(null);

      if (error instanceof ApiError) {
        setLoginError(error.detail);
      } else {
        setLoginError("Could not load current user");
      }

      throw error;
    }
  }, []);

  const signOut = useCallback(async () => {
    try {
      await logout();
    } finally {
      setAccessToken(null);
      setUser(null);
      setLoginError(null);
    }
  }, []);

  const hasRole = useCallback(
    (role: UserRole | UserRole[]) => {
      if (!user) {
        return false;
      }

      if (Array.isArray(role)) {
        return role.includes(user.role);
      }

      return user.role === role;
    },
    [user]
  );

  const refreshCurrentUser = useCallback(async () => {
    if (!accessToken) {
      setUser(null);
      setLoginError(null);
      return;
    }

    setLoginError(null);

    try {
      const currentUser = await getCurrentUser(accessToken);
      setUser(currentUser);
      setLoginError(null);
    } catch (error) {
      setAccessToken(null);
      setUser(null);

      if (error instanceof ApiError) {
        setLoginError(error.detail);
      } else {
        setLoginError("Could not refresh current user");
      }

      throw error;
    }
  }, [accessToken]);

  const value = useMemo<AuthContextValue>(
    () => ({
      user,
      role: user?.role ?? null,
      accessToken,
      isAuthenticated: user !== null,
      isLoading,
      loginError,
      hasRole,
      signIn,
      signOut,
      refreshCurrentUser,
    }),
    [
      accessToken,
      hasRole,
      isLoading,
      loginError,
      refreshCurrentUser,
      signIn,
      signOut,
      user,
    ]
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}
