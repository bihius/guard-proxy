import { render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { AuthContext } from "@/features/auth/auth-context.shared";
import type { AuthContextValue } from "@/features/auth/auth-context.types";
import * as bannedIpsApi from "@/features/banned-ips/api";
import * as logsApi from "@/features/logs/api";
import * as policiesApi from "@/features/policies/api";
import * as vhostsApi from "@/features/vhosts/api";

import { DashboardPage } from "./DashboardPage";

vi.mock("@/features/banned-ips/api");
vi.mock("@/features/logs/api");
vi.mock("@/features/policies/api");
vi.mock("@/features/vhosts/api");
vi.mock("@/features/runtime/use-runtime-status", () => ({
  useRuntimeStatus: () => ({ data: null, isLoading: false, error: null, refresh: vi.fn() }),
}));
vi.mock("@/features/runtime/RuntimeStatusCard", () => ({
  RuntimeStatusCard: () => null,
}));

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

// 2 protected vhosts (active + assigned), plus records that must be excluded:
// one inactive, one active-but-unassigned.
const mockVHosts = [
  { id: 1, is_active: true, policy_id: 10 },
  { id: 2, is_active: true, policy_id: 11 },
  { id: 3, is_active: false, policy_id: 12 },
  { id: 4, is_active: true, policy_id: null },
];
// 1 active policy, plus one inactive that must be excluded.
const mockPolicies = [
  { id: 10, is_active: true },
  { id: 11, is_active: false },
];
// 3 banned entries, plus one merely-tracked (not yet banned) that must be excluded.
const mockBannedIpsResponse = {
  items: [
    { ip: "203.0.113.1", banned: true },
    { ip: "203.0.113.2", banned: true },
    { ip: "203.0.113.3", banned: true },
    { ip: "203.0.113.4", banned: false },
  ],
  total: 4,
};

function renderPage() {
  return render(
    <AuthContext.Provider value={makeAuthContext()}>
      <DashboardPage />
    </AuthContext.Provider>,
  );
}

describe("DashboardPage StatCards", () => {
  it("shows loading skeletons while all fetches are in-flight", () => {
    vi.mocked(vhostsApi.listAllVHosts).mockReturnValue(new Promise(() => undefined));
    vi.mocked(policiesApi.listAllPolicies).mockReturnValue(new Promise(() => undefined));
    vi.mocked(logsApi.fetchLogTotal).mockReturnValue(new Promise(() => undefined));
    vi.mocked(bannedIpsApi.listBannedIps).mockReturnValue(new Promise(() => undefined));

    renderPage();

    expect(screen.getAllByRole("status", { name: /loading/i })).toHaveLength(5);
  });

  it("renders real counts after data loads", async () => {
    vi.mocked(vhostsApi.listAllVHosts).mockResolvedValue(mockVHosts as never);
    vi.mocked(policiesApi.listAllPolicies).mockResolvedValue(mockPolicies as never);
    vi.mocked(logsApi.fetchLogTotal).mockResolvedValue(42);
    vi.mocked(bannedIpsApi.listBannedIps).mockResolvedValue(mockBannedIpsResponse as never);

    renderPage();

    await waitFor(() =>
      expect(screen.queryAllByRole("status", { name: /loading/i })).toHaveLength(0),
    );
    expect(screen.getByText("2")).toBeInTheDocument();  // vhosts
    expect(screen.getByText("1")).toBeInTheDocument();  // policies
    expect(screen.getAllByText("42")).toHaveLength(2);   // blocked + alerts
    expect(screen.getByText("3")).toBeInTheDocument();  // banned IPs (excludes not-yet-banned)
  });

  it("shows — only for the card whose endpoint fails, real counts for others", async () => {
    vi.mocked(vhostsApi.listAllVHosts).mockResolvedValue(mockVHosts as never);
    vi.mocked(policiesApi.listAllPolicies).mockRejectedValue(new Error("Network error"));
    vi.mocked(logsApi.fetchLogTotal).mockResolvedValue(7);
    vi.mocked(bannedIpsApi.listBannedIps).mockResolvedValue(mockBannedIpsResponse as never);

    renderPage();

    await waitFor(() =>
      expect(screen.queryAllByRole("status", { name: /loading/i })).toHaveLength(0),
    );
    expect(screen.getByText("2")).toBeInTheDocument();   // vhosts resolved
    expect(screen.getByText("—")).toBeInTheDocument();   // policies failed
    expect(screen.getAllByText("7")).toHaveLength(2);    // blocked + alerts resolved
    expect(screen.getByText("3")).toBeInTheDocument();   // banned IPs resolved
  });

  it("shows — for all cards when all endpoints fail", async () => {
    vi.mocked(vhostsApi.listAllVHosts).mockRejectedValue(new Error("down"));
    vi.mocked(policiesApi.listAllPolicies).mockRejectedValue(new Error("down"));
    vi.mocked(logsApi.fetchLogTotal).mockRejectedValue(new Error("down"));
    vi.mocked(bannedIpsApi.listBannedIps).mockRejectedValue(new Error("down"));

    renderPage();

    await waitFor(() =>
      expect(screen.queryAllByRole("status", { name: /loading/i })).toHaveLength(0),
    );
    expect(screen.getAllByText("—")).toHaveLength(5);
  });
});
