import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import * as policiesApi from "@/features/policies/api";
import type { RuleOverride } from "@/features/policies/types";
import { AuthContext } from "@/features/auth/auth-context.shared";
import type { AuthContextValue } from "@/features/auth/auth-context.types";
import * as vhostsApi from "@/features/vhosts/api";
import type { Policy, VHostDetail } from "@/features/vhosts/types";

import { VHostDetailPage } from "./VHostDetailPage";

vi.mock("@/features/vhosts/api");
vi.mock("@/features/policies/api");

function makeAuthContext(
  overrides: Partial<AuthContextValue> = {},
): AuthContextValue {
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

const mockPolicies: Policy[] = [
  { id: 1, name: "Default WAF" },
  { id: 2, name: "Strict WAF" },
];

const mockVHost: VHostDetail = {
  id: 1,
  domain: "app.example.com",
  backend_url: "https://backend.internal",
  description: "Primary app",
  ssl_enabled: true, ssl_provider: "none" as const, ssl_expires_at: null,
  is_active: true,
  policy_id: 1,
  created_by: 1,
  created_at: "2026-01-01T00:00:00Z",
  updated_at: "2026-01-02T00:00:00Z",
  policy: {
    id: 1,
    name: "Default WAF",
    description: "Default policy",
    paranoia_level: 2,
    inbound_anomaly_threshold: 5,
    outbound_anomaly_threshold: 4,
    enforcement_mode: "block",
    is_active: true,
    created_by: 1,
    created_at: "2026-01-01T00:00:00Z",
    updated_at: "2026-01-02T00:00:00Z",
  },
};

const mockOverride: RuleOverride = {
  id: 10,
  policy_id: 1,
  rule_id: 942100,
  action: "disable",
  comment: "False positive on search",
  created_at: "2026-01-03T00:00:00Z",
};

const mockOverrides: RuleOverride[] = [mockOverride];

function mockSuccessfulLoad(
  vhost: VHostDetail = mockVHost,
  overrides: RuleOverride[] = mockOverrides,
) {
  vi.mocked(vhostsApi.getVHost).mockResolvedValue(vhost);
  vi.mocked(vhostsApi.listPolicies).mockResolvedValue(mockPolicies);
  vi.mocked(policiesApi.listRuleOverrides).mockResolvedValue(overrides);
}

function renderPage(authOverrides: Partial<AuthContextValue> = {}) {
  return render(
    <AuthContext.Provider value={makeAuthContext(authOverrides)}>
      <MemoryRouter initialEntries={["/vhosts/1"]}>
        <Routes>
          <Route path="/vhosts/:vhostId" element={<VHostDetailPage />} />
        </Routes>
      </MemoryRouter>
    </AuthContext.Provider>,
  );
}

describe("VHostDetailPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(vhostsApi.updateVHost).mockResolvedValue(mockVHost);
    vi.mocked(policiesApi.createRuleOverride).mockResolvedValue(mockOverride);
    vi.mocked(policiesApi.updateRuleOverride).mockResolvedValue(mockOverride);
    vi.mocked(policiesApi.deleteRuleOverride).mockResolvedValue(undefined);
  });

  it("shows loading state initially", () => {
    vi.mocked(vhostsApi.getVHost).mockReturnValue(new Promise(() => undefined));
    vi.mocked(vhostsApi.listPolicies).mockResolvedValue(mockPolicies);

    renderPage();

    expect(screen.getByText(/loading virtual host/i)).toBeInTheDocument();
  });

  it("renders virtual host metadata, assigned policy, and rule overrides", async () => {
    mockSuccessfulLoad();

    renderPage();

    await waitFor(() =>
      expect(
        screen.getByRole("heading", { name: "app.example.com" }),
      ).toBeInTheDocument(),
    );
    expect(screen.getByText("https://backend.internal")).toBeInTheDocument();
    expect(screen.getByDisplayValue("Default WAF")).toBeInTheDocument();
    expect(screen.getByText("942100")).toBeInTheDocument();
    expect(screen.getByText("False positive on search")).toBeInTheDocument();
  });

  it("shows error state and retries loading", async () => {
    vi.mocked(vhostsApi.getVHost)
      .mockRejectedValueOnce(new Error("Network error"))
      .mockResolvedValue(mockVHost);
    vi.mocked(vhostsApi.listPolicies).mockResolvedValue(mockPolicies);
    vi.mocked(policiesApi.listRuleOverrides).mockResolvedValue(mockOverrides);

    renderPage();

    await waitFor(() =>
      expect(screen.getByText(/failed to load virtual host/i)).toBeInTheDocument(),
    );
    await userEvent.click(screen.getByRole("button", { name: /retry/i }));

    await waitFor(() =>
      expect(
        screen.getByRole("heading", { name: "app.example.com" }),
      ).toBeInTheDocument(),
    );
  });

  it("shows no-policy and no-overrides states", async () => {
    mockSuccessfulLoad(
      {
        ...mockVHost,
        policy_id: null,
        policy: null,
      },
      [],
    );

    renderPage();

    await waitFor(() =>
      expect(
        screen.getByRole("heading", { name: "app.example.com" }),
      ).toBeInTheDocument(),
    );
    expect(screen.getAllByText(/no policy assigned/i).length).toBeGreaterThan(0);
    expect(policiesApi.listRuleOverrides).not.toHaveBeenCalled();
  });

  it("lets admins reassign the policy", async () => {
    mockSuccessfulLoad();

    renderPage();

    const policySelect = await screen.findByLabelText("Policy");
    await userEvent.selectOptions(policySelect, "2");
    await userEvent.click(screen.getByRole("button", { name: /save policy/i }));

    await waitFor(() =>
      expect(vhostsApi.updateVHost).toHaveBeenCalledWith("test-token", 1, {
        policy_id: 2,
      }),
    );
  });

  it("lets admins add and edit rule overrides", async () => {
    mockSuccessfulLoad();

    renderPage();

    await userEvent.click(await screen.findByRole("button", { name: /add override/i }));
    await userEvent.clear(screen.getByLabelText("Rule ID"));
    await userEvent.type(screen.getByLabelText("Rule ID"), "941100");
    await userEvent.selectOptions(screen.getByLabelText("Action"), "enable");
    await userEvent.type(screen.getByLabelText("Comment"), "Enable legacy rule");
    await userEvent.click(screen.getByRole("button", { name: "Save" }));

    await waitFor(() =>
      expect(policiesApi.createRuleOverride).toHaveBeenCalledWith(
        "test-token",
        1,
        {
          rule_id: 941100,
          action: "enable",
          comment: "Enable legacy rule",
        },
      ),
    );

    await userEvent.click(await screen.findByRole("button", { name: "Edit" }));
    await userEvent.selectOptions(screen.getByLabelText("Action"), "enable");
    await userEvent.click(screen.getByRole("button", { name: "Save" }));

    await waitFor(() =>
      expect(policiesApi.updateRuleOverride).toHaveBeenCalledWith(
        "test-token",
        1,
        10,
        {
          rule_id: 942100,
          action: "enable",
          comment: "False positive on search",
        },
      ),
    );
  });

  it("lets admins delete rule overrides", async () => {
    mockSuccessfulLoad();

    renderPage();

    await userEvent.click(await screen.findByRole("button", { name: "Delete" }));
    const dialog = screen.getByRole("dialog");
    await userEvent.click(within(dialog).getByRole("button", { name: "Delete" }));

    await waitFor(() =>
      expect(policiesApi.deleteRuleOverride).toHaveBeenCalledWith(
        "test-token",
        1,
        10,
      ),
    );
  });

  it("keeps viewer role read-only", async () => {
    mockSuccessfulLoad();

    renderPage({ hasRole: vi.fn().mockReturnValue(false), role: "viewer" });

    await waitFor(() =>
      expect(
        screen.getByRole("heading", { name: "app.example.com" }),
      ).toBeInTheDocument(),
    );
    expect(screen.queryByRole("button", { name: /save policy/i })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /add override/i })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Edit" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Delete" })).not.toBeInTheDocument();
  });
});
