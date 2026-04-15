import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
  type PropsWithChildren,
} from "react";

import { ApiError } from "@/lib/api-client";
import type { CurrentUser, LoginRequest, UserRole } from "@/types/api";

import { getCurrentUser, login, logout, refreshSession } from "./api";
import { AuthContext } from "./auth-context.shared";
import type { AuthContextValue } from "./auth-context.types";

function isAbortError(error: unknown) {
  return (
    typeof error === "object" &&
    error !== null &&
    "name" in error &&
    error.name === "AbortError"
  );
}

export function AuthProvider({ children }: PropsWithChildren) {
  const [user, setUser] = useState<CurrentUser | null>(null);
  const [accessToken, setAccessToken] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [loginError, setLoginError] = useState<string | null>(null);
  const isMountedRef = useRef(false);
  const currentOperationRef = useRef(0);
  const currentAbortControllerRef = useRef<AbortController | null>(null);

  const isCurrentOperation = useCallback((operationId: number) => {
    return isMountedRef.current && currentOperationRef.current === operationId;
  }, []);

  const finishOperation = useCallback(
    (operationId: number) => {
      if (isCurrentOperation(operationId)) {
        setIsLoading(false);
      }
    },
    [isCurrentOperation]
  );

  const beginOperation = useCallback(() => {
    currentAbortControllerRef.current?.abort();

    const operationId = currentOperationRef.current + 1;
    const abortController = new AbortController();

    currentOperationRef.current = operationId;
    currentAbortControllerRef.current = abortController;

    return {
      operationId,
      signal: abortController.signal,
    };
  }, []);

  useEffect(() => {
    isMountedRef.current = true;

    async function restoreSession() {
      const { operationId, signal } = beginOperation();

      try {
        const tokens = await refreshSession(signal);

        if (signal.aborted || !isCurrentOperation(operationId)) {
          return;
        }

        const currentUser = await getCurrentUser(tokens.access_token, signal);

        if (!isCurrentOperation(operationId)) {
          return;
        }

        setAccessToken(tokens.access_token);
        setUser(currentUser);
        setLoginError(null);
      } catch (error) {
        if (isAbortError(error) || !isCurrentOperation(operationId)) {
          return;
        }

        setAccessToken(null);
        setUser(null);
        setLoginError(null);
      } finally {
        finishOperation(operationId);
      }
    }

    void restoreSession();

    return () => {
      isMountedRef.current = false;
      currentOperationRef.current += 1;
      currentAbortControllerRef.current?.abort();
      currentAbortControllerRef.current = null;
    };
  }, [beginOperation, finishOperation, isCurrentOperation]);

  const signIn = useCallback(async (credentials: LoginRequest) => {
    const { operationId, signal } = beginOperation();

    setLoginError(null);

    try {
      let tokens;

      try {
        tokens = await login(credentials, signal);
      } catch (error) {
        if (isAbortError(error) || !isCurrentOperation(operationId)) {
          return;
        }

        if (error instanceof ApiError) {
          setLoginError(error.detail);
        } else {
          setLoginError("Could not sign in");
        }

        throw error;
      }

      if (signal.aborted || !isCurrentOperation(operationId)) {
        return;
      }

      try {
        const currentUser = await getCurrentUser(tokens.access_token, signal);

        if (!isCurrentOperation(operationId)) {
          return;
        }

        setAccessToken(tokens.access_token);
        setUser(currentUser);
        setLoginError(null);
      } catch (error) {
        if (isAbortError(error) || !isCurrentOperation(operationId)) {
          return;
        }

        setAccessToken(null);
        setUser(null);

        if (error instanceof ApiError) {
          setLoginError(error.detail);
        } else {
          setLoginError("Could not load current user");
        }

        throw error;
      }
    } finally {
      finishOperation(operationId);
    }
  }, [beginOperation, finishOperation, isCurrentOperation]);

  const signOut = useCallback(async () => {
    const { operationId, signal } = beginOperation();

    try {
      await logout(signal);
    } catch (error) {
      if (isAbortError(error) || !isCurrentOperation(operationId)) {
        return;
      }

      throw error;
    } finally {
      if (isCurrentOperation(operationId)) {
        setAccessToken(null);
        setUser(null);
        setLoginError(null);
      }

      finishOperation(operationId);
    }
  }, [beginOperation, finishOperation, isCurrentOperation]);

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
    const { operationId, signal } = beginOperation();
    const token = accessToken;

    if (!token) {
      if (isCurrentOperation(operationId)) {
        setAccessToken(null);
        setUser(null);
        setLoginError(null);
      }

      finishOperation(operationId);
      return;
    }

    setLoginError(null);

    try {
      const currentUser = await getCurrentUser(token, signal);

      if (!isCurrentOperation(operationId)) {
        return;
      }

      setUser(currentUser);
      setLoginError(null);
    } catch (error) {
      if (isAbortError(error) || !isCurrentOperation(operationId)) {
        return;
      }

      setAccessToken(null);
      setUser(null);

      if (error instanceof ApiError) {
        setLoginError(error.detail);
      } else {
        setLoginError("Could not refresh current user");
      }

      throw error;
    } finally {
      finishOperation(operationId);
    }
  }, [accessToken, beginOperation, finishOperation, isCurrentOperation]);

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
