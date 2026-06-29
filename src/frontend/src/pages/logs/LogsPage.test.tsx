import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { AuthContext } from "@/features/auth/auth-context.shared";
import type { AuthContextValue } from "@/features/auth/auth-context.types";
import * as logsApi from "@/features/logs/api";
import * as vhostsApi from "@/features/vhosts/api";

import { LogsPage } from "./LogsPage";

vi.mock("@/features/logs/api");
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

const mockPolicies = [{ id: 1, name: "Default Policy" }];

const mockLog = {
  id: 42,
  producer_event_id: null,
  event_at: "2026-06-01T10:00:00Z",
  vhost: "app.example.com",
  action: "deny" as const,
  source_ip: "203.0.113.10",
  method: "POST",
  request_uri: "/login",
  status_code: 403,
  rule_id: 942100,
  rule_message: "SQL injection attack detected",
  anomaly_score: 15,
  paranoia_level: 2,
  severity: "error" as const,
  message: null,
  raw_context: null,
  vhost_id: 1,
  policy_id: 1,
  policy_name: "Default Policy",
};

const mockListResponse = { items: [mockLog], total: 1, page: 1, page_size: 50 };
const emptyListResponse = { items: [], total: 0, page: 1, page_size: 50 };

function renderPage() {
  return render(
    <AuthContext.Provider value={makeAuthContext()}>
      <LogsPage />
    </AuthContext.Provider>,
  );
}

describe("LogsPage", () => {
  it("shows loading state initially", () => {
    vi.mocked(logsApi.listLogs).mockReturnValue(new Promise(() => undefined));
    vi.mocked(vhostsApi.listAllPolicies).mockReturnValue(new Promise(() => undefined));

    renderPage();
    expect(screen.getByText(/loading logs/i)).toBeInTheDocument();
  });

  it("renders log rows from API response", async () => {
    vi.mocked(logsApi.listLogs).mockResolvedValue(mockListResponse);
    vi.mocked(vhostsApi.listAllPolicies).mockResolvedValue(mockPolicies);

    renderPage();

    await waitFor(() =>
      expect(screen.getByText("app.example.com")).toBeInTheDocument(),
    );
    expect(screen.getByText("POST")).toBeInTheDocument();
    expect(screen.getByText("deny")).toBeInTheDocument();
    expect(screen.getByText("15")).toBeInTheDocument();
  });

  it("shows error state on API failure", async () => {
    vi.mocked(logsApi.listLogs).mockRejectedValue(new Error("Network error"));
    vi.mocked(vhostsApi.listAllPolicies).mockRejectedValue(new Error("Network error"));

    renderPage();

    await waitFor(() =>
      expect(screen.getByText(/failed to load logs/i)).toBeInTheDocument(),
    );
    expect(screen.getByRole("button", { name: /retry/i })).toBeInTheDocument();
  });

  it("shows empty state when no logs match", async () => {
    vi.mocked(logsApi.listLogs).mockResolvedValue(emptyListResponse);
    vi.mocked(vhostsApi.listAllPolicies).mockResolvedValue([]);

    renderPage();

    await waitFor(() =>
      expect(screen.getByText(/no events found/i)).toBeInTheDocument(),
    );
  });

  it("hides filter inputs until the Filters toggle is opened", async () => {
    vi.mocked(logsApi.listLogs).mockResolvedValue(mockListResponse);
    vi.mocked(vhostsApi.listAllPolicies).mockResolvedValue(mockPolicies);

    renderPage();
    await waitFor(() => expect(screen.getByText("app.example.com")).toBeInTheDocument());

    expect(screen.queryByLabelText(/vhost/i)).not.toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: /filters/i }));

    expect(screen.getByLabelText(/vhost/i)).toBeInTheDocument();
  });

  it("shows an active filter count badge after applying filters", async () => {
    vi.mocked(logsApi.listLogs).mockResolvedValue(mockListResponse);
    vi.mocked(vhostsApi.listAllPolicies).mockResolvedValue(mockPolicies);

    renderPage();
    await waitFor(() => expect(screen.getByText("app.example.com")).toBeInTheDocument());

    await userEvent.click(screen.getByRole("button", { name: /filters/i }));
    await userEvent.type(screen.getByLabelText(/vhost/i), "api.example.com");
    await userEvent.click(screen.getByRole("button", { name: /apply/i }));

    await waitFor(() =>
      expect(screen.getByRole("button", { name: /filters/i })).toHaveTextContent("1"),
    );
  });

  it("labels the allow filter option to clarify it means flagged-but-allowed", async () => {
    vi.mocked(logsApi.listLogs).mockResolvedValue(mockListResponse);
    vi.mocked(vhostsApi.listAllPolicies).mockResolvedValue(mockPolicies);

    renderPage();
    await waitFor(() => expect(screen.getByText("app.example.com")).toBeInTheDocument());

    await userEvent.click(screen.getByRole("button", { name: /filters/i }));

    expect(
      screen.getByRole("option", { name: "Allowed (flagged)" }),
    ).toBeInTheDocument();
  });

  it("applying filters re-fetches with filter params", async () => {
    vi.mocked(logsApi.listLogs).mockResolvedValue(mockListResponse);
    vi.mocked(vhostsApi.listAllPolicies).mockResolvedValue(mockPolicies);

    renderPage();
    await waitFor(() => expect(screen.getByText("app.example.com")).toBeInTheDocument());

    await userEvent.click(screen.getByRole("button", { name: /filters/i }));
    await userEvent.type(screen.getByLabelText(/vhost/i), "api.example.com");
    await userEvent.click(screen.getByRole("button", { name: /apply/i }));

    await waitFor(() =>
      expect(vi.mocked(logsApi.listLogs)).toHaveBeenCalledWith(
        "test-token",
        expect.objectContaining({ vhost: "api.example.com", page: 1 }),
        expect.anything(),
      ),
    );
  });

  it("applies the new severity, method, source IP, rule ID and min score filters", async () => {
    vi.mocked(logsApi.listLogs).mockResolvedValue(mockListResponse);
    vi.mocked(vhostsApi.listAllPolicies).mockResolvedValue(mockPolicies);

    renderPage();
    await waitFor(() => expect(screen.getByText("app.example.com")).toBeInTheDocument());

    await userEvent.click(screen.getByRole("button", { name: /filters/i }));
    await userEvent.selectOptions(screen.getByLabelText(/severity/i), "critical");
    await userEvent.type(screen.getByLabelText(/^method$/i), "POST");
    await userEvent.type(screen.getByLabelText(/source ip/i), "203.0.113.10");
    await userEvent.type(screen.getByLabelText(/rule id/i), "942290");
    await userEvent.type(screen.getByLabelText(/min anomaly score/i), "5");
    await userEvent.click(screen.getByRole("button", { name: /apply/i }));

    await waitFor(() =>
      expect(vi.mocked(logsApi.listLogs)).toHaveBeenCalledWith(
        "test-token",
        expect.objectContaining({
          severity: "critical",
          method: "POST",
          source_ip: "203.0.113.10",
          rule_id: 942290,
          min_score: 5,
          page: 1,
        }),
        expect.anything(),
      ),
    );
  });

  it("applies from and to date/time filters", async () => {
    vi.mocked(logsApi.listLogs).mockResolvedValue(mockListResponse);
    vi.mocked(vhostsApi.listAllPolicies).mockResolvedValue(mockPolicies);

    renderPage();
    await waitFor(() => expect(screen.getByText("app.example.com")).toBeInTheDocument());

    await userEvent.click(screen.getByRole("button", { name: /filters/i }));
    fireEvent.change(screen.getByLabelText("From date"), {
      target: { value: "2026-06-01" },
    });
    fireEvent.change(screen.getByLabelText("From time"), {
      target: { value: "08:30" },
    });
    fireEvent.change(screen.getByLabelText("To date"), {
      target: { value: "2026-06-02" },
    });
    fireEvent.change(screen.getByLabelText("To time"), {
      target: { value: "17:45" },
    });
    await userEvent.click(screen.getByRole("button", { name: /apply/i }));

    await waitFor(() =>
      expect(vi.mocked(logsApi.listLogs)).toHaveBeenCalledWith(
        "test-token",
        expect.objectContaining({
          date_from: "2026-06-01T08:30",
          date_to: "2026-06-02T17:45",
          page: 1,
        }),
        expect.anything(),
      ),
    );
  });

  it("clearing filters resets to empty params", async () => {
    vi.mocked(logsApi.listLogs).mockResolvedValue(mockListResponse);
    vi.mocked(vhostsApi.listAllPolicies).mockResolvedValue(mockPolicies);

    renderPage();
    await waitFor(() => expect(screen.getByText("app.example.com")).toBeInTheDocument());

    await userEvent.click(screen.getByRole("button", { name: /filters/i }));
    await userEvent.type(screen.getByLabelText(/vhost/i), "something");
    await userEvent.click(screen.getByRole("button", { name: /clear/i }));

    await waitFor(() =>
      expect(vi.mocked(logsApi.listLogs)).toHaveBeenLastCalledWith(
        "test-token",
        expect.objectContaining({ vhost: undefined, page: 1 }),
        expect.anything(),
      ),
    );
  });

  it("View button opens detail modal with log fields", async () => {
    vi.mocked(logsApi.listLogs).mockResolvedValue(mockListResponse);
    vi.mocked(vhostsApi.listAllPolicies).mockResolvedValue(mockPolicies);

    renderPage();
    await waitFor(() => expect(screen.getByText("app.example.com")).toBeInTheDocument());

    await userEvent.click(screen.getByRole("button", { name: /view/i }));

    const dialog = screen.getByRole("dialog");
    expect(within(dialog).getByText("Event details")).toBeInTheDocument();
    expect(within(dialog).getByText("SQL injection attack detected")).toBeInTheDocument();
    expect(within(dialog).getByText("203.0.113.10")).toBeInTheDocument();
    expect(within(dialog).getByText("Default Policy")).toBeInTheDocument();
    expect(within(dialog).queryByText("VHost ID")).not.toBeInTheDocument();
    expect(within(dialog).queryByText("Policy ID")).not.toBeInTheDocument();
  });

  it("wraps raw context in the detail modal", async () => {
    vi.mocked(logsApi.listLogs).mockResolvedValue({
      ...mockListResponse,
      items: [
        {
          ...mockLog,
          raw_context: {
            long_value: "x".repeat(120),
          },
        },
      ],
    });
    vi.mocked(vhostsApi.listAllPolicies).mockResolvedValue(mockPolicies);

    renderPage();
    await waitFor(() => expect(screen.getByText("app.example.com")).toBeInTheDocument());

    await userEvent.click(screen.getByRole("button", { name: /view/i }));
    await userEvent.click(screen.getByRole("button", { name: /show raw context/i }));

    const rawContext = screen.getByText((content, element) => {
      return element?.tagName.toLowerCase() === "pre" && content.includes("long_value");
    });
    expect(rawContext).toHaveClass("whitespace-pre-wrap");
    expect(rawContext).toHaveClass("break-words");
    expect(rawContext).toHaveClass("overflow-x-hidden");
  });
});
