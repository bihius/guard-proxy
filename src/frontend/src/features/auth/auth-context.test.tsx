import { render, screen, waitFor } from "@testing-library/react";
import { useAuth } from "@/hooks/use-auth";
import { describe, expect, it, vi } from "vitest";

import type { CurrentUser } from "@/types/api";

import { AuthProvider } from "./auth-context";

vi.mock("./api", () => ({
  getCurrentUser: vi.fn(),
  login: vi.fn(),
  logout: vi.fn(),
  refreshSession: vi.fn(),
}));

import { getCurrentUser, refreshSession } from "./api";

const mockedRefreshSession = vi.mocked(refreshSession);
const mockedGetCurrentUser = vi.mocked(getCurrentUser);

const currentUser: CurrentUser = {
  id: 1,
  email: "admin@example.com",
  full_name: "Admin User",
  role: "admin",
  is_active: true,
  created_at: "2026-03-29T00:00:00Z",
  updated_at: "2026-03-29T00:00:00Z",
};

function AuthConsumer() {
  const { isAuthenticated, isLoading, user } = useAuth();

  return (
    <>
      <span>{isLoading ? "loading" : "ready"}</span>
      <span>{isAuthenticated ? "authenticated" : "anonymous"}</span>
      <span>{user?.email ?? "no-user"}</span>
    </>
  );
}

describe("AuthProvider", () => {
  it("restores a session through refresh and me calls", async () => {
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
      expect(screen.getByText("ready")).toBeInTheDocument();
    });

    expect(screen.getByText("authenticated")).toBeInTheDocument();
    expect(screen.getByText(currentUser.email)).toBeInTheDocument();
  });

  it("falls back to anonymous when refresh fails", async () => {
    mockedRefreshSession.mockRejectedValueOnce(new Error("No session"));

    render(
      <AuthProvider>
        <AuthConsumer />
      </AuthProvider>,
    );

    await waitFor(() => {
      expect(screen.getByText("ready")).toBeInTheDocument();
    });

    expect(screen.getByText("anonymous")).toBeInTheDocument();
    expect(screen.getByText("no-user")).toBeInTheDocument();
  });
});
