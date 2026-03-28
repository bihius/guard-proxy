import {
  useCallback,
  useEffect,
  useMemo,
  useState,
  type PropsWithChildren,
} from "react";

import { ApiError } from "@/lib/api-client";
import type { CurrentUser, LoginRequest } from "@/types/api";

import { getCurrentUser, login } from "./api";
import { AuthContext } from "./auth-context.shared";
import type { AuthContextValue } from "./auth-context.types";
import {
  clearAuthTokens,
  readAuthTokens,
  writeAuthTokens,
} from "./storage";

export function AuthProvider({ children }: PropsWithChildren) {
  const [user, setUser] = useState<CurrentUser | null>(null);
  const [accessToken, setAccessToken] = useState<string | null>(null);
  const [refreshToken, setRefreshToken] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [loginError, setLoginError] = useState<string | null>(null);

  useEffect(() => {
    const storedTokens = readAuthTokens();

    if (!storedTokens) {
      setIsLoading(false);
      return;
    }

    setAccessToken(storedTokens.accessToken);
    setRefreshToken(storedTokens.refreshToken);

    void getCurrentUser(storedTokens.accessToken)
      .then((currentUser) => {
        setUser(currentUser);
      })
      .catch(() => {
        clearAuthTokens();
        setAccessToken(null);
        setRefreshToken(null);
        setUser(null);
      })
      .finally(() => {
        setIsLoading(false);
      });
  }, []);

  const signIn = useCallback(async (credentials: LoginRequest) => {
    setLoginError(null);
    const tokens = await login(credentials);

    writeAuthTokens({
      accessToken: tokens.access_token,
      refreshToken: tokens.refresh_token,
    });

    setAccessToken(tokens.access_token);
    setRefreshToken(tokens.refresh_token);

    try {
      const currentUser = await getCurrentUser(tokens.access_token);
      setUser(currentUser);
    } catch (error) {
      clearAuthTokens();
      setAccessToken(null);
      setRefreshToken(null);
      setUser(null);

      if (error instanceof ApiError) {
        setLoginError(error.detail);
      } else {
        setLoginError("Could not load current user");
      }

      throw error;
    }
  }, []);

  const signOut = useCallback(() => {
    clearAuthTokens();
    setAccessToken(null);
    setRefreshToken(null);
    setUser(null);
    setLoginError(null);
  }, []);

  const refreshCurrentUser = useCallback(async () => {
    if (!accessToken) {
      setUser(null);
      return;
    }

    const currentUser = await getCurrentUser(accessToken);
    setUser(currentUser);
  }, [accessToken]);

  const value = useMemo<AuthContextValue>(
    () => ({
      user,
      accessToken,
      refreshToken,
      isAuthenticated: user !== null,
      isLoading,
      loginError,
      signIn,
      signOut,
      refreshCurrentUser,
    }),
    [
      accessToken,
      isLoading,
      loginError,
      refreshCurrentUser,
      refreshToken,
      signIn,
      signOut,
      user,
    ]
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}
