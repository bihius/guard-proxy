import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { useAuth } from "@/hooks/use-auth";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { ApiError } from "@/lib/api-client";
import type { CurrentUser } from "@/types/api";
import type { TokenResponse } from "@/types/api";

import { AuthProvider } from "./auth-context";

vi.mock("./api", () => ({
  getCurrentUser: vi.fn(),
  login: vi.fn(),
  logout: vi.fn(),
  refreshSession: vi.fn(),
}));

import { getCurrentUser, login, logout, refreshSession } from "./api";

const mockedLogin = vi.mocked(login);
const mockedLogout = vi.mocked(logout);
const mockedRefreshSession = vi.mocked(refreshSession);
const mockedGetCurrentUser = vi.mocked(getCurrentUser);
const credentials = {
  email: "admin@example.com",
  password: "secret",
};

function createUser(overrides: Partial<CurrentUser> = {}): CurrentUser {
  return {
    id: 1,
    email: "admin@example.com",
    full_name: "Admin User",
    role: "admin",
    is_active: true,
    created_at: "2026-03-29T00:00:00Z",
    updated_at: "2026-03-29T00:00:00Z",
    ...overrides,
  };
}

function createDeferred<T>() {
  let resolve!: (value: T) => void;
  let reject!: (reason?: unknown) => void;

  const promise = new Promise<T>((resolvePromise, rejectPromise) => {
    resolve = resolvePromise;
    reject = rejectPromise;
  });

  return {
    promise,
    resolve,
    reject,
  };
}

function AuthConsumer() {
  const {
    accessToken,
    isAuthenticated,
    isLoading,
    loginError,
    refreshCurrentUser,
    signIn,
    signOut,
    user,
  } = useAuth();

  return (
    <>
      <span data-testid="loading">{isLoading ? "loading" : "ready"}</span>
      <span data-testid="auth">{isAuthenticated ? "authenticated" : "anonymous"}</span>
      <span data-testid="user">{user?.email ?? "no-user"}</span>
      <span data-testid="token">{accessToken ?? "no-token"}</span>
      <span data-testid="error">{loginError ?? "no-error"}</span>
      <button
        type="button"
        onClick={() => {
          void signIn(credentials).catch(() => undefined);
        }}
      >
        sign in
      </button>
      <button
        type="button"
        onClick={() => {
          void signOut().catch(() => undefined);
        }}
      >
        sign out
      </button>
      <button
        type="button"
        onClick={() => {
          void refreshCurrentUser().catch(() => undefined);
        }}
      >
        refresh user
      </button>
    </>
  );
}

async function flushPromises() {
  await act(async () => {
    await Promise.resolve();
  });
}

async function waitForReady() {
  await waitFor(() => {
    expect(screen.getByTestId("loading")).toHaveTextContent("ready");
  });
}

describe("AuthProvider", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("restores a session through refresh and me calls", async () => {
    const currentUser = createUser();

    mockedRefreshSession.mockResolvedValueOnce({
      access_token: "fresh-access",
      token_type: "bearer",
    });
    mockedGetCurrentUser.mockResolvedValueOnce(currentUser);

    render(
      <AuthProvider>
        <AuthConsumer />
      </AuthProvider>,
    );

    await waitFor(() => {
      expect(screen.getByTestId("loading")).toHaveTextContent("ready");
    });

    expect(screen.getByTestId("auth")).toHaveTextContent("authenticated");
    expect(screen.getByTestId("user")).toHaveTextContent(currentUser.email);
    expect(screen.getByTestId("token")).toHaveTextContent("fresh-access");
  });

  it("falls back to anonymous when refresh fails", async () => {
    mockedRefreshSession.mockRejectedValueOnce(new Error("No session"));

    render(
      <AuthProvider>
        <AuthConsumer />
      </AuthProvider>,
    );

    await waitFor(() => {
      expect(screen.getByTestId("loading")).toHaveTextContent("ready");
    });

    expect(screen.getByTestId("auth")).toHaveTextContent("anonymous");
    expect(screen.getByTestId("user")).toHaveTextContent("no-user");
    expect(screen.getByTestId("token")).toHaveTextContent("no-token");
  });

  it("lets sign in replace an in-flight session restore", async () => {
    const refreshDeferred = createDeferred<TokenResponse>();
    const signedInUser = createUser({
      email: "signed-in@example.com",
      full_name: "Signed In User",
    });

    mockedRefreshSession.mockReturnValueOnce(refreshDeferred.promise);
    mockedLogin.mockResolvedValueOnce({
      access_token: "login-access",
      token_type: "bearer",
    });
    mockedGetCurrentUser.mockResolvedValueOnce(signedInUser);

    render(
      <AuthProvider>
        <AuthConsumer />
      </AuthProvider>,
    );

    fireEvent.click(screen.getByRole("button", { name: "sign in" }));

    await waitFor(() => {
      expect(screen.getByTestId("loading")).toHaveTextContent("ready");
      expect(screen.getByTestId("auth")).toHaveTextContent("authenticated");
    });

    const restoreSignal = mockedRefreshSession.mock.calls[0]?.[0];
    expect(restoreSignal).toBeInstanceOf(AbortSignal);
    expect(restoreSignal?.aborted).toBe(true);

    await act(async () => {
      refreshDeferred.resolve({
        access_token: "restored-access",
        token_type: "bearer",
      });
    });
    await flushPromises();

    expect(mockedGetCurrentUser).toHaveBeenCalledTimes(1);
    expect(screen.getByTestId("user")).toHaveTextContent(signedInUser.email);
    expect(screen.getByTestId("token")).toHaveTextContent("login-access");
  });

  it("keeps logout as the winner over a stale login response", async () => {
    const loginUserDeferred = createDeferred<CurrentUser>();

    mockedRefreshSession.mockRejectedValueOnce(new Error("No session"));
    mockedLogin.mockResolvedValueOnce({
      access_token: "login-access",
      token_type: "bearer",
    });
    mockedGetCurrentUser.mockReturnValueOnce(loginUserDeferred.promise);
    mockedLogout.mockResolvedValueOnce(undefined);

    render(
      <AuthProvider>
        <AuthConsumer />
      </AuthProvider>,
    );

    await waitForReady();

    fireEvent.click(screen.getByRole("button", { name: "sign in" }));

    await waitFor(() => {
      expect(mockedGetCurrentUser).toHaveBeenCalledTimes(1);
    });

    fireEvent.click(screen.getByRole("button", { name: "sign out" }));

    await waitFor(() => {
      expect(screen.getByTestId("auth")).toHaveTextContent("anonymous");
      expect(screen.getByTestId("user")).toHaveTextContent("no-user");
    });

    const loginSignal = mockedGetCurrentUser.mock.calls[0]?.[1];
    expect(loginSignal).toBeInstanceOf(AbortSignal);
    expect(loginSignal?.aborted).toBe(true);

    await act(async () => {
      loginUserDeferred.resolve(
        createUser({
          email: "late-login@example.com",
        }),
      );
    });
    await flushPromises();

    expect(screen.getByTestId("auth")).toHaveTextContent("anonymous");
    expect(screen.getByTestId("user")).toHaveTextContent("no-user");
    expect(screen.getByTestId("token")).toHaveTextContent("no-token");
  });

  it("applies only the latest overlapping refreshCurrentUser result", async () => {
    const restoredUser = createUser();
    const staleRefreshDeferred = createDeferred<CurrentUser>();
    const latestRefreshDeferred = createDeferred<CurrentUser>();
    const latestUser = createUser({
      email: "latest@example.com",
      full_name: "Latest User",
    });

    mockedRefreshSession.mockResolvedValueOnce({
      access_token: "session-access",
      token_type: "bearer",
    });
    mockedGetCurrentUser
      .mockResolvedValueOnce(restoredUser)
      .mockReturnValueOnce(staleRefreshDeferred.promise)
      .mockReturnValueOnce(latestRefreshDeferred.promise);

    render(
      <AuthProvider>
        <AuthConsumer />
      </AuthProvider>,
    );

    await waitForReady();

    fireEvent.click(screen.getByRole("button", { name: "refresh user" }));
    fireEvent.click(screen.getByRole("button", { name: "refresh user" }));

    await waitFor(() => {
      expect(mockedGetCurrentUser).toHaveBeenCalledTimes(3);
    });

    const staleRefreshSignal = mockedGetCurrentUser.mock.calls[1]?.[1];
    const latestRefreshSignal = mockedGetCurrentUser.mock.calls[2]?.[1];
    expect(staleRefreshSignal?.aborted).toBe(true);
    expect(latestRefreshSignal?.aborted).toBe(false);

    await act(async () => {
      staleRefreshDeferred.resolve(
        createUser({
          email: "stale@example.com",
        }),
      );
    });
    await flushPromises();

    expect(screen.getByTestId("user")).toHaveTextContent(restoredUser.email);

    await act(async () => {
      latestRefreshDeferred.resolve(latestUser);
    });

    await waitFor(() => {
      expect(screen.getByTestId("user")).toHaveTextContent(latestUser.email);
    });
  });

  it("ignores a stale refresh failure after a newer refresh succeeds", async () => {
    const restoredUser = createUser();
    const staleRefreshDeferred = createDeferred<CurrentUser>();
    const latestRefreshDeferred = createDeferred<CurrentUser>();
    const latestUser = createUser({
      email: "updated@example.com",
      full_name: "Updated User",
    });

    mockedRefreshSession.mockResolvedValueOnce({
      access_token: "session-access",
      token_type: "bearer",
    });
    mockedGetCurrentUser
      .mockResolvedValueOnce(restoredUser)
      .mockReturnValueOnce(staleRefreshDeferred.promise)
      .mockReturnValueOnce(latestRefreshDeferred.promise);

    render(
      <AuthProvider>
        <AuthConsumer />
      </AuthProvider>,
    );

    await waitForReady();

    fireEvent.click(screen.getByRole("button", { name: "refresh user" }));
    fireEvent.click(screen.getByRole("button", { name: "refresh user" }));

    await waitFor(() => {
      expect(mockedGetCurrentUser).toHaveBeenCalledTimes(3);
    });

    await act(async () => {
      latestRefreshDeferred.resolve(latestUser);
    });

    await waitFor(() => {
      expect(screen.getByTestId("user")).toHaveTextContent(latestUser.email);
    });

    await act(async () => {
      staleRefreshDeferred.reject(new ApiError(401, "Session expired"));
    });
    await flushPromises();

    expect(screen.getByTestId("auth")).toHaveTextContent("authenticated");
    expect(screen.getByTestId("user")).toHaveTextContent(latestUser.email);
    expect(screen.getByTestId("token")).toHaveTextContent("session-access");
    expect(screen.getByTestId("error")).toHaveTextContent("no-error");
  });

  it("aborts restore requests on unmount", async () => {
    const refreshDeferred = createDeferred<TokenResponse>();

    mockedRefreshSession.mockReturnValueOnce(refreshDeferred.promise);

    const { unmount } = render(
      <AuthProvider>
        <AuthConsumer />
      </AuthProvider>,
    );

    const restoreSignal = mockedRefreshSession.mock.calls[0]?.[0];
    expect(restoreSignal).toBeInstanceOf(AbortSignal);
    expect(restoreSignal?.aborted).toBe(false);

    unmount();

    expect(restoreSignal?.aborted).toBe(true);

    await act(async () => {
      refreshDeferred.resolve({
        access_token: "restored-access",
        token_type: "bearer",
      });
    });
    await flushPromises();

    expect(mockedGetCurrentUser).not.toHaveBeenCalled();
  });
});
