import { render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";

import { AuthContext } from "@/features/auth/auth-context.shared";
import type { AuthContextValue } from "@/features/auth/auth-context.types";

import { ProtectedRoute, PublicOnlyRoute } from "./protected-route";

function makeAuthContextValue(
  overrides: Partial<AuthContextValue> = {},
): AuthContextValue {
  return {
    user: null,
    role: null,
    accessToken: null,
    isAuthenticated: false,
    isLoading: false,
    loginError: null,
    hasRole: vi.fn().mockReturnValue(false),
    signIn: vi.fn(),
    signOut: vi.fn(),
    refreshCurrentUser: vi.fn(),
    ...overrides,
  };
}

describe("route guards", () => {
  it("redirects anonymous users away from protected routes", () => {
    render(
      <AuthContext.Provider value={makeAuthContextValue()}>
        <MemoryRouter initialEntries={["/dashboard"]}>
          <Routes>
            <Route element={<ProtectedRoute />}>
              <Route path="/dashboard" element={<div>Private dashboard</div>} />
            </Route>
            <Route path="/login" element={<div>Login screen</div>} />
          </Routes>
        </MemoryRouter>
      </AuthContext.Provider>,
    );

    expect(screen.getByText("Login screen")).toBeInTheDocument();
  });

  it("redirects authenticated users away from login", () => {
    render(
      <AuthContext.Provider
        value={makeAuthContextValue({
          isAuthenticated: true,
          user: {
            id: 1,
            email: "admin@example.com",
            full_name: "Admin User",
            role: "admin",
            is_active: true,
            created_at: "2026-03-29T00:00:00Z",
            updated_at: "2026-03-29T00:00:00Z",
          },
          role: "admin",
        })}
      >
        <MemoryRouter initialEntries={["/login"]}>
          <Routes>
            <Route element={<PublicOnlyRoute />}>
              <Route path="/login" element={<div>Login screen</div>} />
            </Route>
            <Route path="/dashboard" element={<div>Dashboard screen</div>} />
          </Routes>
        </MemoryRouter>
      </AuthContext.Provider>,
    );

    expect(screen.getByText("Dashboard screen")).toBeInTheDocument();
  });
});
