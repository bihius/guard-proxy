import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";

import { AuthContext } from "@/features/auth/auth-context.shared";
import type { AuthContextValue } from "@/features/auth/auth-context.types";
import * as dashboardApi from "@/features/dashboard/api";
import type {
  OverviewResponse,
  TimeseriesResponse,
  TopResponse,
} from "@/features/dashboard/types";
import * as logsApi from "@/features/logs/api";

import { DashboardPage } from "./DashboardPage";

vi.mock("@/features/dashboard/api");
vi.mock("@/features/logs/api");
vi.mock("@/features/runtime/use-runtime-status", () => ({
  useRuntimeStatus: () => ({
    data: {
      frontend_contract_version: "1",
      deployment_state: "deployed",
      generated_config: {
        can_generate: true,
        checksum: "abc123def456789",
        generated_at: "2026-07-29T10:00:00Z",
        error: null,
      },
      latest_validation: null,
      latest_reload: {
        id: 1,
        operation_type: "reload",
        status: "success",
        config_checksum: "abc123def456789",
        message: null,
        created_at: "2026-07-29T10:00:00Z",
      },
    },
    isLoading: false,
    error: null,
    refresh: vi.fn(),
  }),
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

const mockOverview: OverviewResponse = {
  window: "24h",
  start_at: "2026-07-28T12:00:00Z",
  end_at: "2026-07-29T12:00:00Z",
  requests: { current: 4128, previous: 4000, delta_pct: 3.2 },
  blocked: { current: 312, previous: 250, delta_pct: 24.8 },
  monitored: { current: 48, previous: 52, delta_pct: -7.7 },
  critical: { current: 1, previous: 0, delta_pct: null },
  banned_ips: 3,
  protected_vhosts: 2,
  total_vhosts: 5,
  active_policies: 1,
};

const mockTimeseries: TimeseriesResponse = {
  window: "24h",
  start_at: "2026-07-28T12:00:00Z",
  end_at: "2026-07-29T12:00:00Z",
  bucket_seconds: 3600,
  buckets: [
    { bucket_at: "2026-07-28T12:00:00Z", allow: 10, deny: 2, monitor: 1 },
    { bucket_at: "2026-07-28T13:00:00Z", allow: 20, deny: 5, monitor: 0 },
  ],
};

const emptyTimeseries: TimeseriesResponse = {
  ...mockTimeseries,
  buckets: [
    { bucket_at: "2026-07-28T12:00:00Z", allow: 0, deny: 0, monitor: 0 },
    { bucket_at: "2026-07-28T13:00:00Z", allow: 0, deny: 0, monitor: 0 },
  ],
};

const mockTop: TopResponse = {
  window: "24h",
  start_at: "2026-07-28T12:00:00Z",
  end_at: "2026-07-29T12:00:00Z",
  limit: 5,
  rules: [
    { rule_id: 942100, rule_message: "SQL Injection Attack Detected", count: 120 },
    { rule_id: 941100, rule_message: "XSS Attack Detected", count: 40 },
  ],
  source_ips: [
    { source_ip: "203.0.113.5", count: 90, is_banned: true },
    { source_ip: "203.0.113.9", count: 12, is_banned: false },
  ],
  vhosts: [{ vhost: "app.example.com", vhost_id: 1, count: 160 }],
};

const mockLog = {
  id: 42,
  producer_event_id: null,
  event_at: "2026-07-29T11:59:00Z",
  vhost: "app.example.com",
  action: "deny" as const,
  source_ip: "203.0.113.5",
  method: "POST",
  request_uri: "/login",
  status_code: 403,
  rule_id: 942100,
  rule_message: "SQL injection attack detected",
  anomaly_score: 15,
  paranoia_level: 2,
  severity: "critical" as const,
  message: null,
  raw_context: null,
  vhost_id: 1,
  policy_id: 1,
  policy_name: "Default Policy",
};

function mockHappyPath() {
  vi.mocked(dashboardApi.fetchOverview).mockResolvedValue(mockOverview);
  vi.mocked(dashboardApi.fetchTimeseries).mockResolvedValue(mockTimeseries);
  vi.mocked(dashboardApi.fetchTop).mockResolvedValue(mockTop);
  vi.mocked(logsApi.listLogs).mockResolvedValue({
    items: [mockLog],
    total: 1,
    page: 1,
    page_size: 8,
  });
}

function renderPage(
  initialEntry = "/dashboard",
  auth: Partial<AuthContextValue> = {},
) {
  return render(
    <MemoryRouter initialEntries={[initialEntry]}>
      <AuthContext.Provider value={makeAuthContext(auth)}>
        <DashboardPage />
      </AuthContext.Provider>
    </MemoryRouter>,
  );
}

describe("DashboardPage", () => {
  it("shows loading skeletons while every section is in flight", () => {
    vi.mocked(dashboardApi.fetchOverview).mockReturnValue(new Promise(() => undefined));
    vi.mocked(dashboardApi.fetchTimeseries).mockReturnValue(
      new Promise(() => undefined),
    );
    vi.mocked(dashboardApi.fetchTop).mockReturnValue(new Promise(() => undefined));
    vi.mocked(logsApi.listLogs).mockReturnValue(new Promise(() => undefined));

    renderPage();

    expect(
      screen.getByRole("status", { name: /loading activity chart/i }),
    ).toBeInTheDocument();
    expect(
      screen.getAllByRole("status", { name: /loading/i }).length,
    ).toBeGreaterThan(1);
  });

  it("renders metrics, deltas and the activity chart once loaded", async () => {
    mockHappyPath();

    renderPage();

    expect(await screen.findByText("4,128")).toBeInTheDocument();
    expect(screen.getByText("312")).toBeInTheDocument();
    expect(screen.getByText("48")).toBeInTheDocument();
    // Critical went 0 -> 1: no percentage baseline exists, so it reads "new".
    expect(screen.getByText("new")).toBeInTheDocument();
    expect(
      screen.getByRole("img", { name: /request activity across 2 intervals/i }),
    ).toBeInTheDocument();
  });

  it("exposes the chart data as a table so it is not colour-only", async () => {
    mockHappyPath();

    renderPage();

    const table = await screen.findByRole("table", {
      name: /request activity per interval/i,
    });
    expect(within(table).getByRole("columnheader", { name: "Blocked" })).toBeVisible();
    expect(within(table).getAllByRole("row")).toHaveLength(3); // header + 2 buckets
  });

  it("requests the window taken from the URL", async () => {
    mockHappyPath();

    renderPage("/dashboard?window=7d");

    await waitFor(() =>
      expect(dashboardApi.fetchOverview).toHaveBeenCalledWith(
        "test-token",
        "7d",
        expect.anything(),
      ),
    );
    const tab = screen.getByRole("tab", { name: "7d" });
    expect(tab).toHaveAttribute("aria-selected", "true");
  });

  it("refetches with the newly selected window", async () => {
    mockHappyPath();
    const user = userEvent.setup();

    renderPage();
    await screen.findByText("4,128");

    await user.click(screen.getByRole("tab", { name: "1h" }));

    await waitFor(() =>
      expect(dashboardApi.fetchTimeseries).toHaveBeenCalledWith(
        "test-token",
        "1h",
        expect.anything(),
      ),
    );
  });

  it("moves between windows with the arrow keys", async () => {
    mockHappyPath();
    const user = userEvent.setup();

    renderPage();
    await screen.findByText("4,128");

    const selected = screen.getByRole("tab", { name: "24h" });
    selected.focus();
    await user.keyboard("{ArrowRight}");

    await waitFor(() =>
      expect(screen.getByRole("tab", { name: "7d" })).toHaveAttribute(
        "aria-selected",
        "true",
      ),
    );

    // Keeping focus on the moved-to tab is what makes a second press work at
    // all, so assert it explicitly rather than inferring it from the move.
    expect(screen.getByRole("tab", { name: "7d" })).toHaveFocus();

    await user.keyboard("{ArrowRight}");

    await waitFor(() =>
      expect(screen.getByRole("tab", { name: "30d" })).toHaveAttribute(
        "aria-selected",
        "true",
      ),
    );
  });

  it("lists top rules and marks banned source IPs", async () => {
    mockHappyPath();

    renderPage();

    expect(await screen.findByText("942100")).toBeInTheDocument();
    expect(screen.getByText("SQL Injection Attack Detected")).toBeInTheDocument();
    // The IP also appears in the recent-blocks feed, hence getAllByText.
    expect(screen.getAllByText("203.0.113.5").length).toBeGreaterThan(0);
    expect(screen.getByText("Banned")).toBeInTheDocument();
  });

  it("shows an empty state instead of a flat all-zero chart", async () => {
    mockHappyPath();
    vi.mocked(dashboardApi.fetchTimeseries).mockResolvedValue(emptyTimeseries);

    renderPage();

    expect(await screen.findByText(/no traffic in the last 24 hours/i)).toBeInTheDocument();
    expect(screen.queryByRole("img", { name: /request activity/i })).toBeNull();
  });

  it("keeps the chart when only the metrics endpoint fails", async () => {
    mockHappyPath();
    vi.mocked(dashboardApi.fetchOverview).mockRejectedValue(new Error("boom"));

    renderPage();

    expect(await screen.findByText(/could not load metrics/i)).toBeInTheDocument();
    expect(
      screen.getByRole("img", { name: /request activity across 2 intervals/i }),
    ).toBeInTheDocument();
  });

  it("reports an unreachable Runtime API without blanking the dashboard", async () => {
    mockHappyPath();
    vi.mocked(dashboardApi.fetchOverview).mockResolvedValue({
      ...mockOverview,
      banned_ips: null,
    });

    renderPage();

    expect(await screen.findByText(/runtime api unavailable/i)).toBeInTheDocument();
    expect(screen.getByText("312")).toBeInTheDocument();
  });

  it("hides the banned-IP tile from viewers", async () => {
    mockHappyPath();

    renderPage("/dashboard", { role: "viewer", hasRole: vi.fn().mockReturnValue(false) });

    await screen.findByText("4,128");
    expect(screen.queryByText("Banned IPs")).toBeNull();
  });

  it("shows deployment state and the protected-vhost inventory", async () => {
    mockHappyPath();

    renderPage();

    expect(await screen.findByText("Deployed")).toBeInTheDocument();
    expect(screen.getByText("2 / 5")).toBeInTheDocument();
    // Generated and running checksums match, so the truncated value appears twice.
    expect(screen.getAllByText("abc123def456")).toHaveLength(2);
  });

  it("lists recent blocks", async () => {
    mockHappyPath();

    renderPage();

    expect(await screen.findByText(/POST \/login/)).toBeInTheDocument();
    expect(logsApi.listLogs).toHaveBeenCalledWith(
      "test-token",
      expect.objectContaining({ action: "deny", page_size: 8 }),
      expect.anything(),
    );
  });
});
