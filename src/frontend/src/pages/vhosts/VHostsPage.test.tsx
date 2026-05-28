import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { AuthContext } from "@/features/auth/auth-context.shared";
import type { AuthContextValue } from "@/features/auth/auth-context.types";
import * as vhostsApi from "@/features/vhosts/api";

import { VHostsPage } from "./VHostsPage";

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

const mockVHosts = [
  {
    id: 1,
    domain: "app.example.com",
    backend_url: "https://backend.internal",
    description: null,
    ssl_enabled: true,
    is_active: true,
    policy_id: 1,
    created_by: 1,
    created_at: "2026-01-01T00:00:00Z",
    updated_at: "2026-01-01T00:00:00Z",
  },
];

const mockPolicies = [{ id: 1, name: "Default" }];

function renderPage(authOverrides: Partial<AuthContextValue> = {}) {
  return render(
    <AuthContext.Provider value={makeAuthContext(authOverrides)}>
      <VHostsPage />
    </AuthContext.Provider>,
  );
}

describe("VHostsPage", () => {
  it("shows loading state initially", () => {
    vi.mocked(vhostsApi.listVHosts).mockReturnValue(new Promise(() => undefined));
    vi.mocked(vhostsApi.listPolicies).mockReturnValue(new Promise(() => undefined));

    renderPage();
    expect(screen.getByText(/loading virtual hosts/i)).toBeInTheDocument();
  });

  it("renders rows from API response", async () => {
    vi.mocked(vhostsApi.listVHosts).mockResolvedValue(mockVHosts);
    vi.mocked(vhostsApi.listPolicies).mockResolvedValue(mockPolicies);

    renderPage();

    await waitFor(() =>
      expect(screen.getByText("app.example.com")).toBeInTheDocument(),
    );
    expect(screen.getByText("Default")).toBeInTheDocument();
    expect(screen.getByText("Active")).toBeInTheDocument();
  });

  it("shows error state and retry button on failure", async () => {
    vi.mocked(vhostsApi.listVHosts).mockRejectedValue(new Error("Network error"));
    vi.mocked(vhostsApi.listPolicies).mockRejectedValue(new Error("Network error"));

    renderPage();

    await waitFor(() =>
      expect(screen.getByText(/failed to load virtual hosts/i)).toBeInTheDocument(),
    );
    expect(screen.getByRole("button", { name: /retry/i })).toBeInTheDocument();
  });

  it("shows empty state when no vhosts", async () => {
    vi.mocked(vhostsApi.listVHosts).mockResolvedValue([]);
    vi.mocked(vhostsApi.listPolicies).mockResolvedValue([]);

    renderPage();

    await waitFor(() =>
      expect(screen.getByText(/no virtual hosts yet/i)).toBeInTheDocument(),
    );
  });

  it("admin sees New vhost button and Edit/Delete actions", async () => {
    vi.mocked(vhostsApi.listVHosts).mockResolvedValue(mockVHosts);
    vi.mocked(vhostsApi.listPolicies).mockResolvedValue(mockPolicies);

    renderPage({ hasRole: vi.fn().mockReturnValue(true) });

    await waitFor(() =>
      expect(screen.getByText("app.example.com")).toBeInTheDocument(),
    );
    expect(screen.getByRole("button", { name: /new vhost/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /edit/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /delete/i })).toBeInTheDocument();
  });

  it("viewer does not see New vhost button or Edit/Delete actions", async () => {
    vi.mocked(vhostsApi.listVHosts).mockResolvedValue(mockVHosts);
    vi.mocked(vhostsApi.listPolicies).mockResolvedValue(mockPolicies);

    renderPage({ hasRole: vi.fn().mockReturnValue(false) });

    await waitFor(() =>
      expect(screen.getByText("app.example.com")).toBeInTheDocument(),
    );
    expect(screen.queryByRole("button", { name: /new vhost/i })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /edit/i })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /delete/i })).not.toBeInTheDocument();
  });

  it("retry button calls refresh after error", async () => {
    vi.mocked(vhostsApi.listVHosts)
      .mockRejectedValueOnce(new Error("Network error"))
      .mockResolvedValue(mockVHosts);
    vi.mocked(vhostsApi.listPolicies)
      .mockRejectedValueOnce(new Error("Network error"))
      .mockResolvedValue(mockPolicies);

    renderPage();

    await waitFor(() =>
      expect(screen.getByRole("button", { name: /retry/i })).toBeInTheDocument(),
    );
    await userEvent.click(screen.getByRole("button", { name: /retry/i }));
    await waitFor(() =>
      expect(screen.getByText("app.example.com")).toBeInTheDocument(),
    );
  });
});
