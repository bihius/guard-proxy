import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";

import { AuthContext } from "@/features/auth/auth-context.shared";
import type { AuthContextValue } from "@/features/auth/auth-context.types";
import * as policiesApi from "@/features/policies/api";
import * as vhostsApi from "@/features/vhosts/api";

import { PoliciesPage } from "./PoliciesPage";

vi.mock("@/features/policies/api");
vi.mock("@/features/vhosts/api");

function makeAuthContext(overrides: Partial<AuthContextValue> = {}): AuthContextValue {
  return {
    user: null,
    role: "admin",
    accessToken: "test-token",
    isAuthenticated: true,
    isLoading: false,
    loginError: null,
    hasRole: vi.fn().mockReturnValue(true),
    signIn: vi.fn(),
    signOut: vi.fn(),
    refreshCurrentUser: vi.fn(),
    ...overrides,
  };
}

const mockPolicies = [
  {
    id: 1,
    name: "Default WAF",
    description: null,
    paranoia_level: 2 as const,
    inbound_anomaly_threshold: 5,
    outbound_anomaly_threshold: 4,
    enforcement_mode: "block" as const,
    is_active: true,
    created_by: 1,
    created_at: "2026-01-01T00:00:00Z",
    updated_at: "2026-01-01T00:00:00Z",
  },
];

const mockPolicyListResponse = {
  items: mockPolicies,
  total: 1,
  page: 1,
  per_page: 50,
};

const mockVHostListResponse = {
  items: [
    {
      id: 1,
      domain: "app.example.com",
      backend_url: "https://backend.internal",
      description: null,
      ssl_enabled: false,
      ssl_provider: "none" as const,
      ssl_expires_at: null,
      is_active: true,
      policy_id: 1,
      created_by: 1,
      created_at: "2026-01-01T00:00:00Z",
      updated_at: "2026-01-01T00:00:00Z",
    },
  ],
  total: 1,
  page: 1,
  per_page: 50,
};

function renderPage(authOverrides: Partial<AuthContextValue> = {}) {
  return render(
    <AuthContext.Provider value={makeAuthContext(authOverrides)}>
      <MemoryRouter initialEntries={["/policies"]}>
        <Routes>
          <Route path="/policies" element={<PoliciesPage />} />
          <Route path="/policies/:policyId" element={<p>Policy detail page</p>} />
        </Routes>
      </MemoryRouter>
    </AuthContext.Provider>,
  );
}

describe("PoliciesPage", () => {
  it("renders paginated policy rows from the API response", async () => {
    vi.mocked(policiesApi.listPolicies).mockResolvedValue(mockPolicyListResponse);
    vi.mocked(vhostsApi.listAllVHosts).mockResolvedValue(mockVHostListResponse.items);

    renderPage();

    await waitFor(() =>
      expect(screen.getByText("Default WAF")).toBeInTheDocument(),
    );
    expect(screen.getByText("Block")).toBeInTheDocument();
    expect(screen.getByText("Page 1 of 1 · 1 policies")).toBeInTheDocument();
  });

  it("requests the next page and filters by policy search", async () => {
    vi.mocked(policiesApi.listPolicies).mockResolvedValue({
      ...mockPolicyListResponse,
      total: 75,
    });
    vi.mocked(vhostsApi.listAllVHosts).mockResolvedValue(mockVHostListResponse.items);

    renderPage();

    await waitFor(() =>
      expect(screen.getByText("Default WAF")).toBeInTheDocument(),
    );
    await userEvent.click(screen.getByRole("button", { name: /next/i }));

    await waitFor(() =>
      expect(policiesApi.listPolicies).toHaveBeenLastCalledWith(
        "test-token",
        { page: 2, per_page: 50, q: undefined },
        expect.any(AbortSignal),
      ),
    );

    await userEvent.type(screen.getByLabelText(/search policies/i), "strict");

    await waitFor(() =>
      expect(policiesApi.listPolicies).toHaveBeenLastCalledWith(
        "test-token",
        { page: 1, per_page: 50, q: "strict" },
        expect.any(AbortSignal),
      ),
    );
  });

  it("does not show admin actions to viewers", async () => {
    vi.mocked(policiesApi.listPolicies).mockResolvedValue(mockPolicyListResponse);
    vi.mocked(vhostsApi.listAllVHosts).mockResolvedValue(mockVHostListResponse.items);

    renderPage({ hasRole: vi.fn().mockReturnValue(false), role: "viewer" });

    await waitFor(() =>
      expect(screen.getByText("Default WAF")).toBeInTheDocument(),
    );
    expect(screen.queryByRole("button", { name: /new policy/i })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /edit/i })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /delete/i })).not.toBeInTheDocument();
  });
});
