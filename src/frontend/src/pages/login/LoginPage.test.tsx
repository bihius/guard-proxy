import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";

import { AuthContext } from "@/features/auth/auth-context.shared";
import type { AuthContextValue } from "@/features/auth/auth-context.types";

import { LoginPage } from "./LoginPage";

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

describe("LoginPage", () => {
  it("announces login errors for assistive technology", () => {
    render(
      <AuthContext.Provider
        value={makeAuthContextValue({ loginError: "Invalid credentials" })}
      >
        <MemoryRouter>
          <LoginPage />
        </MemoryRouter>
      </AuthContext.Provider>,
    );

    expect(screen.getByRole("alert")).toHaveTextContent("Invalid credentials");
  });
});
