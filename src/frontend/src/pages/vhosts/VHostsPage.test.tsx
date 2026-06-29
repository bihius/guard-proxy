import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
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
    backends: [
      {
        id: 1,
        vhost_id: 1,
        url: "https://backend.internal",
        is_active: true,
        health_check_enabled: true,
        health_check_path: "/",
        health_check_interval_seconds: 5,
        health_check_fall: 3,
        health_check_rise: 2,
        created_at: "2026-01-01T00:00:00Z",
        updated_at: "2026-01-01T00:00:00Z",
      },
    ],
    description: null,
    ssl_enabled: true, ssl_provider: "none" as const, ssl_expires_at: null,
    is_active: true,
    policy_id: 1,
    created_by: 1,
    created_at: "2026-01-01T00:00:00Z",
    updated_at: "2026-01-01T00:00:00Z",
  },
];

const mockPolicies = [{ id: 1, name: "Default" }];
const mockVHostListResponse = {
  items: mockVHosts,
  total: 1,
  page: 1,
  per_page: 50,
};
const emptyVHostListResponse = {
  items: [],
  total: 0,
  page: 1,
  per_page: 50,
};

function renderPage(authOverrides: Partial<AuthContextValue> = {}) {
  return render(
    <AuthContext.Provider value={makeAuthContext(authOverrides)}>
      <MemoryRouter initialEntries={["/vhosts"]}>
        <Routes>
          <Route path="/vhosts" element={<VHostsPage />} />
          <Route path="/vhosts/:vhostId" element={<p>VHost detail page</p>} />
        </Routes>
      </MemoryRouter>
    </AuthContext.Provider>,
  );
}

describe("VHostsPage", () => {
  it("shows loading state initially", () => {
    vi.mocked(vhostsApi.listVHosts).mockReturnValue(new Promise(() => undefined));
    vi.mocked(vhostsApi.listAllPolicies).mockReturnValue(new Promise(() => undefined));

    renderPage();
    expect(screen.getByText(/loading virtual hosts/i)).toBeInTheDocument();
  });

  it("renders rows from API response", async () => {
    vi.mocked(vhostsApi.listVHosts).mockResolvedValue(mockVHostListResponse);
    vi.mocked(vhostsApi.listAllPolicies).mockResolvedValue(mockPolicies);

    renderPage();

    await waitFor(() =>
      expect(screen.getByText("app.example.com")).toBeInTheDocument(),
    );
    expect(screen.getByText("Default")).toBeInTheDocument();
    expect(screen.getByText("Active")).toBeInTheDocument();
  });

  it("shows error state and retry button on failure", async () => {
    vi.mocked(vhostsApi.listVHosts).mockRejectedValue(new Error("Network error"));
    vi.mocked(vhostsApi.listAllPolicies).mockRejectedValue(new Error("Network error"));

    renderPage();

    await waitFor(() =>
      expect(screen.getByText(/failed to load virtual hosts/i)).toBeInTheDocument(),
    );
    expect(screen.getByRole("button", { name: /retry/i })).toBeInTheDocument();
  });

  it("shows empty state when no vhosts", async () => {
    vi.mocked(vhostsApi.listVHosts).mockResolvedValue(emptyVHostListResponse);
    vi.mocked(vhostsApi.listAllPolicies).mockResolvedValue([]);

    renderPage();

    await waitFor(() =>
      expect(screen.getByText(/no virtual hosts found/i)).toBeInTheDocument(),
    );
  });

  it("admin sees New vhost button and Edit/Delete actions", async () => {
    vi.mocked(vhostsApi.listVHosts).mockResolvedValue(mockVHostListResponse);
    vi.mocked(vhostsApi.listAllPolicies).mockResolvedValue(mockPolicies);

    renderPage({ hasRole: vi.fn().mockReturnValue(true) });

    await waitFor(() =>
      expect(screen.getByText("app.example.com")).toBeInTheDocument(),
    );
    expect(screen.getByRole("button", { name: /new vhost/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /edit/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /delete/i })).toBeInTheDocument();
  });

  it("viewer does not see New vhost button or Edit/Delete actions", async () => {
    vi.mocked(vhostsApi.listVHosts).mockResolvedValue(mockVHostListResponse);
    vi.mocked(vhostsApi.listAllPolicies).mockResolvedValue(mockPolicies);

    renderPage({ hasRole: vi.fn().mockReturnValue(false) });

    await waitFor(() =>
      expect(screen.getByText("app.example.com")).toBeInTheDocument(),
    );
    expect(screen.queryByRole("button", { name: /new vhost/i })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /edit/i })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /delete/i })).not.toBeInTheDocument();
  });

  it("navigates to the vhost detail page when a row is clicked", async () => {
    vi.mocked(vhostsApi.listVHosts).mockResolvedValue(mockVHostListResponse);
    vi.mocked(vhostsApi.listAllPolicies).mockResolvedValue(mockPolicies);

    renderPage();

    await waitFor(() =>
      expect(screen.getByText("app.example.com")).toBeInTheDocument(),
    );
    await userEvent.click(screen.getByText("app.example.com"));

    expect(screen.getByText("VHost detail page")).toBeInTheDocument();
  });

  it("does not navigate when row action buttons are clicked", async () => {
    vi.mocked(vhostsApi.listVHosts).mockResolvedValue(mockVHostListResponse);
    vi.mocked(vhostsApi.listAllPolicies).mockResolvedValue(mockPolicies);

    renderPage({ hasRole: vi.fn().mockReturnValue(true) });

    await waitFor(() =>
      expect(screen.getByText("app.example.com")).toBeInTheDocument(),
    );
    await userEvent.click(screen.getByRole("button", { name: /edit/i }));

    expect(screen.queryByText("VHost detail page")).not.toBeInTheDocument();
    expect(screen.getByText("Edit virtual host")).toBeInTheDocument();
  });

  it("retry button calls refresh after error", async () => {
    vi.mocked(vhostsApi.listVHosts)
      .mockRejectedValueOnce(new Error("Network error"))
      .mockResolvedValue(mockVHostListResponse);
    vi.mocked(vhostsApi.listAllPolicies)
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

  it("requests the next page and filters by domain search", async () => {
    vi.mocked(vhostsApi.listVHosts).mockResolvedValue({
      ...mockVHostListResponse,
      total: 75,
    });
    vi.mocked(vhostsApi.listAllPolicies).mockResolvedValue(mockPolicies);

    renderPage();

    await waitFor(() =>
      expect(screen.getByText("app.example.com")).toBeInTheDocument(),
    );
    await userEvent.click(screen.getByRole("button", { name: /next/i }));

    await waitFor(() =>
      expect(vhostsApi.listVHosts).toHaveBeenLastCalledWith(
        "test-token",
        { page: 2, per_page: 50, q: undefined },
        expect.any(AbortSignal),
      ),
    );

    await userEvent.type(screen.getByLabelText(/search virtual hosts/i), "api");

    await waitFor(() =>
      expect(vhostsApi.listVHosts).toHaveBeenLastCalledWith(
        "test-token",
        { page: 1, per_page: 50, q: "api" },
        expect.any(AbortSignal),
      ),
    );
  });
});
