import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import * as policiesApi from "@/features/policies/api";
import { AuthContext } from "@/features/auth/auth-context.shared";
import type { AuthContextValue } from "@/features/auth/auth-context.types";
import type {
  CustomRule,
  PolicyDetail,
  RuleExclusion,
  RuleOverride,
} from "@/features/policies/types";

import { PolicyDetailPage } from "./PolicyDetailPage";

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

const mockOverride: RuleOverride = {
  id: 10,
  policy_id: 1,
  rule_id: 942100,
  action: "disable",
  comment: "False positive on search",
  created_at: "2026-01-03T00:00:00Z",
};

const mockExclusion: RuleExclusion = {
  id: 20,
  policy_id: 1,
  rule_id: 941100,
  target_type: "args",
  target_value: "token",
  scope_path: "/api/login",
  comment: "Login token false positive",
  created_at: "2026-01-04T00:00:00Z",
};

const mockCustomRule: CustomRule = {
  id: 30,
  policy_id: 1,
  rule_id: 9000001,
  phase: "request_headers",
  variables: "REQUEST_HEADERS:User-Agent",
  operator: "rx",
  operator_argument: "(?i)curl",
  actions: "deny,status:403,log",
  comment: "Block curl",
  is_active: true,
  created_at: "2026-01-05T00:00:00Z",
  updated_at: "2026-01-05T00:00:00Z",
};

const mockPolicy: PolicyDetail = {
  id: 1,
  name: "Default WAF",
  description: "Default policy",
  paranoia_level: 2,
  inbound_anomaly_threshold: 5,
  outbound_anomaly_threshold: 4,
  enforcement_mode: "block",
  is_active: true,
  ddos_protection_enabled: false,
  rate_limit_requests: 100,
  rate_limit_window_seconds: 10,
  max_connections_per_ip: 20,
  auto_ban_enabled: false,
  ban_threshold: 10,
  ban_duration_seconds: 600,
  created_by: 1,
  created_at: "2026-01-01T00:00:00Z",
  updated_at: "2026-01-02T00:00:00Z",
  rule_overrides: [mockOverride],
  rule_exclusions: [mockExclusion],
  custom_rules: [mockCustomRule],
};

function mockSuccessfulLoad(policy: PolicyDetail = mockPolicy) {
  vi.mocked(policiesApi.getPolicy).mockResolvedValue(policy);
}

function renderPage(authOverrides: Partial<AuthContextValue> = {}) {
  return render(
    <AuthContext.Provider value={makeAuthContext(authOverrides)}>
      <MemoryRouter initialEntries={["/policies/1"]}>
        <Routes>
          <Route path="/policies/:policyId" element={<PolicyDetailPage />} />
        </Routes>
      </MemoryRouter>
    </AuthContext.Provider>,
  );
}

describe("PolicyDetailPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(policiesApi.createRuleOverride).mockResolvedValue(mockOverride);
    vi.mocked(policiesApi.updateRuleOverride).mockResolvedValue(mockOverride);
    vi.mocked(policiesApi.deleteRuleOverride).mockResolvedValue(undefined);
    vi.mocked(policiesApi.createRuleExclusion).mockResolvedValue(mockExclusion);
    vi.mocked(policiesApi.updateRuleExclusion).mockResolvedValue(mockExclusion);
    vi.mocked(policiesApi.deleteRuleExclusion).mockResolvedValue(undefined);
    vi.mocked(policiesApi.createCustomRule).mockResolvedValue(mockCustomRule);
    vi.mocked(policiesApi.updateCustomRule).mockResolvedValue(mockCustomRule);
    vi.mocked(policiesApi.deleteCustomRule).mockResolvedValue(undefined);
  });

  it("shows loading state initially", () => {
    vi.mocked(policiesApi.getPolicy).mockReturnValue(new Promise(() => undefined));

    renderPage();

    expect(screen.getByText(/loading policy/i)).toBeInTheDocument();
  });

  it("renders policy settings, overrides, exclusions, and custom rules", async () => {
    mockSuccessfulLoad();

    renderPage();

    await waitFor(() =>
      expect(screen.getByRole("heading", { name: "Default WAF" })).toBeInTheDocument(),
    );
    expect(screen.getByText("942100")).toBeInTheDocument();
    expect(screen.getByText("False positive on search")).toBeInTheDocument();
    expect(screen.getByText("token")).toBeInTheDocument();
    expect(screen.getByText("/api/login")).toBeInTheDocument();
    expect(screen.getByText("9000001")).toBeInTheDocument();
    expect(screen.getByText("REQUEST_HEADERS:User-Agent")).toBeInTheDocument();
  });

  it("shows error state and retries loading", async () => {
    vi.mocked(policiesApi.getPolicy)
      .mockRejectedValueOnce(new Error("Network error"))
      .mockResolvedValue(mockPolicy);

    renderPage();

    await waitFor(() =>
      expect(screen.getByText(/failed to load policy/i)).toBeInTheDocument(),
    );
    await userEvent.click(screen.getByRole("button", { name: /retry/i }));

    await waitFor(() =>
      expect(screen.getByRole("heading", { name: "Default WAF" })).toBeInTheDocument(),
    );
  });

  it("lets admins add, edit, and delete rule overrides", async () => {
    mockSuccessfulLoad();

    renderPage();

    await userEvent.click(await screen.findByRole("button", { name: /add override/i }));
    await userEvent.clear(screen.getByLabelText("Rule ID"));
    await userEvent.type(screen.getByLabelText("Rule ID"), "941100");
    await userEvent.selectOptions(screen.getByLabelText("Action"), "enable");
    await userEvent.click(screen.getByRole("button", { name: "Save" }));

    await waitFor(() =>
      expect(policiesApi.createRuleOverride).toHaveBeenCalledWith("test-token", 1, {
        rule_id: 941100,
        action: "enable",
        comment: null,
      }),
    );

    const overrideRow = (await screen.findByText("942100")).closest("tr");
    if (!overrideRow) throw new Error("override row not found");

    await userEvent.click(within(overrideRow).getByRole("button", { name: "Edit" }));
    await userEvent.selectOptions(screen.getByLabelText("Action"), "enable");
    await userEvent.click(screen.getByRole("button", { name: "Save" }));

    await waitFor(() =>
      expect(policiesApi.updateRuleOverride).toHaveBeenCalledWith("test-token", 1, 10, {
        rule_id: 942100,
        action: "enable",
        comment: "False positive on search",
      }),
    );

    const refreshedOverrideRow = (await screen.findByText("942100")).closest("tr");
    if (!refreshedOverrideRow) throw new Error("override row not found");

    await userEvent.click(
      within(refreshedOverrideRow).getByRole("button", { name: "Delete" }),
    );
    const dialog = screen.getByRole("dialog");
    await userEvent.click(within(dialog).getByRole("button", { name: "Delete" }));

    await waitFor(() =>
      expect(policiesApi.deleteRuleOverride).toHaveBeenCalledWith("test-token", 1, 10),
    );
  });

  it("lets admins add a rule exclusion", async () => {
    mockSuccessfulLoad();

    renderPage();

    await userEvent.click(await screen.findByRole("button", { name: /add exclusion/i }));
    await userEvent.type(screen.getByLabelText("Rule ID"), "941200");
    await userEvent.type(screen.getByLabelText("Target value"), "csrf_token");
    await userEvent.click(screen.getByRole("button", { name: "Save" }));

    await waitFor(() =>
      expect(policiesApi.createRuleExclusion).toHaveBeenCalledWith("test-token", 1, {
        rule_id: 941200,
        target_type: "args",
        target_value: "csrf_token",
        scope_path: null,
        comment: null,
      }),
    );
  });

  it("lets admins edit and delete rule exclusions", async () => {
    mockSuccessfulLoad();

    renderPage();

    const exclusionRow = (await screen.findByText("token")).closest("tr");
    if (!exclusionRow) throw new Error("exclusion row not found");

    await userEvent.click(within(exclusionRow).getByRole("button", { name: "Edit" }));
    await userEvent.selectOptions(screen.getByLabelText("Target type"), "request_headers");
    await userEvent.clear(screen.getByLabelText("Target value"));
    await userEvent.type(screen.getByLabelText("Target value"), "X-CSRF-Token");
    await userEvent.clear(screen.getByLabelText("Scope path"));
    await userEvent.type(screen.getByLabelText("Scope path"), "/api/session");
    await userEvent.click(screen.getByRole("button", { name: "Save" }));

    await waitFor(() =>
      expect(policiesApi.updateRuleExclusion).toHaveBeenCalledWith(
        "test-token",
        1,
        20,
        {
          rule_id: 941100,
          target_type: "request_headers",
          target_value: "X-CSRF-Token",
          scope_path: "/api/session",
          comment: "Login token false positive",
        },
      ),
    );

    const refreshedExclusionRow = (await screen.findByText("token")).closest("tr");
    if (!refreshedExclusionRow) throw new Error("exclusion row not found");

    await userEvent.click(
      within(refreshedExclusionRow).getByRole("button", { name: "Delete" }),
    );
    const dialog = screen.getByRole("dialog");
    await userEvent.click(within(dialog).getByRole("button", { name: "Delete" }));

    await waitFor(() =>
      expect(policiesApi.deleteRuleExclusion).toHaveBeenCalledWith(
        "test-token",
        1,
        20,
      ),
    );
  });

  it("rejects an out-of-range custom rule ID before calling the API", async () => {
    mockSuccessfulLoad();

    renderPage();

    await userEvent.click(await screen.findByRole("button", { name: /add custom rule/i }));
    await userEvent.type(screen.getByLabelText("Rule ID"), "123");
    await userEvent.type(screen.getByLabelText("Variables"), "ARGS");
    await userEvent.type(screen.getByLabelText("Operator argument"), "(?i)bad");
    await userEvent.type(screen.getByLabelText("Actions"), "deny");
    await userEvent.click(screen.getByRole("button", { name: "Save" }));

    expect(
      await screen.findByText(/rule id must be between 9000000 and 9099999/i),
    ).toBeInTheDocument();
    expect(policiesApi.createCustomRule).not.toHaveBeenCalled();
  });

  it("lets admins add a custom rule", async () => {
    mockSuccessfulLoad();

    renderPage();

    await userEvent.click(await screen.findByRole("button", { name: /add custom rule/i }));
    await userEvent.type(screen.getByLabelText("Rule ID"), "9000002");
    await userEvent.type(screen.getByLabelText("Variables"), "ARGS");
    await userEvent.type(screen.getByLabelText("Operator argument"), "(?i)bad");
    await userEvent.type(screen.getByLabelText("Actions"), "deny,status:403");
    await userEvent.click(screen.getByRole("button", { name: "Save" }));

    await waitFor(() =>
      expect(policiesApi.createCustomRule).toHaveBeenCalledWith("test-token", 1, {
        rule_id: 9000002,
        phase: "request_headers",
        variables: "ARGS",
        operator: "rx",
        operator_argument: "(?i)bad",
        actions: "deny,status:403",
        comment: null,
        is_active: true,
      }),
    );
  });

  it("lets admins edit and delete custom rules", async () => {
    mockSuccessfulLoad();

    renderPage();

    const customRuleRow = (
      await screen.findByText("REQUEST_HEADERS:User-Agent")
    ).closest("tr");
    if (!customRuleRow) throw new Error("custom rule row not found");

    await userEvent.click(within(customRuleRow).getByRole("button", { name: "Edit" }));
    await userEvent.selectOptions(screen.getByLabelText("Phase"), "request_body");
    await userEvent.clear(screen.getByLabelText("Variables"));
    await userEvent.type(screen.getByLabelText("Variables"), "ARGS");
    await userEvent.clear(screen.getByLabelText("Actions"));
    await userEvent.type(screen.getByLabelText("Actions"), "deny,status:403");
    await userEvent.click(screen.getByRole("checkbox", { name: "Active" }));
    await userEvent.click(screen.getByRole("button", { name: "Save" }));

    await waitFor(() =>
      expect(policiesApi.updateCustomRule).toHaveBeenCalledWith(
        "test-token",
        1,
        30,
        {
          rule_id: 9000001,
          phase: "request_body",
          variables: "ARGS",
          operator: "rx",
          operator_argument: "(?i)curl",
          actions: "deny,status:403",
          comment: "Block curl",
          is_active: false,
        },
      ),
    );

    const refreshedCustomRuleRow = (
      await screen.findByText("REQUEST_HEADERS:User-Agent")
    ).closest("tr");
    if (!refreshedCustomRuleRow) throw new Error("custom rule row not found");

    await userEvent.click(
      within(refreshedCustomRuleRow).getByRole("button", { name: "Delete" }),
    );
    const dialog = screen.getByRole("dialog");
    await userEvent.click(within(dialog).getByRole("button", { name: "Delete" }));

    await waitFor(() =>
      expect(policiesApi.deleteCustomRule).toHaveBeenCalledWith("test-token", 1, 30),
    );
  });

  it("keeps viewer role read-only across all tuning sections", async () => {
    mockSuccessfulLoad();

    renderPage({ hasRole: vi.fn().mockReturnValue(false), role: "viewer" });

    await waitFor(() =>
      expect(screen.getByRole("heading", { name: "Default WAF" })).toBeInTheDocument(),
    );
    expect(screen.queryByRole("button", { name: /add override/i })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /add exclusion/i })).not.toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: /add custom rule/i }),
    ).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Edit" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Delete" })).not.toBeInTheDocument();
  });
});
