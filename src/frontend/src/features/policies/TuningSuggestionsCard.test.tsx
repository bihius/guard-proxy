import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { AuthContext } from "@/features/auth/auth-context.shared";
import type { AuthContextValue } from "@/features/auth/auth-context.types";
import * as policiesApi from "@/features/policies/api";
import type { TuningSuggestion } from "@/features/policies/types";

import { TuningSuggestionsCard } from "./TuningSuggestionsCard";

vi.mock("@/features/policies/api");

const suggestion: TuningSuggestion = {
  id: 7,
  policy_id: 3,
  rule_id: 942100,
  rule_message: "SQL Injection Attack Detected via libinjection",
  target_type: "args",
  target_value: "q",
  scope_path: "/search",
  confidence: 86,
  event_count: 12,
  source_ip_count: 9,
  first_seen_at: "2026-09-24T08:00:00",
  last_seen_at: "2026-09-24T18:30:00",
  sample_log_ids: [1, 2, 3],
  status: "pending",
  rule_exclusion_id: null,
  created_at: "2026-09-24T19:00:00",
  updated_at: "2026-09-24T19:00:00",
  resolved_at: null,
};

function renderCard(isAdmin = true, onExclusionCreated = vi.fn()) {
  const auth = {
    user: null,
    role: isAdmin ? "admin" : "viewer",
    accessToken: "test-token",
    isAuthenticated: true,
    isLoading: false,
    loginError: null,
    hasRole: vi.fn().mockReturnValue(isAdmin),
    signIn: vi.fn(),
    signOut: vi.fn(),
    refreshCurrentUser: vi.fn(),
  } as AuthContextValue;
  render(
    <MemoryRouter>
      <AuthContext.Provider value={auth}>
        <TuningSuggestionsCard policyId={3} onExclusionCreated={onExclusionCreated} />
      </AuthContext.Provider>
    </MemoryRouter>,
  );
  return onExclusionCreated;
}

describe("TuningSuggestionsCard", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(policiesApi.listTuningSuggestions).mockResolvedValue([suggestion]);
  });

  it("approves the reviewed, edited exclusion through the suggestion", async () => {
    vi.mocked(policiesApi.approveTuningSuggestion).mockResolvedValue({
      ...suggestion,
      status: "approved",
    });
    const onExclusionCreated = renderCard();

    await userEvent.click(await screen.findByRole("button", { name: "Review" }));
    expect(screen.getByLabelText("Target value")).toHaveValue("q");
    await userEvent.clear(screen.getByLabelText("Scope path"));
    await userEvent.type(screen.getByLabelText("Scope path"), "/search/basic");
    await userEvent.click(screen.getByRole("button", { name: "Approve" }));

    await waitFor(() =>
      expect(policiesApi.approveTuningSuggestion).toHaveBeenCalledWith("test-token", 3, 7, {
        rule_id: 942100,
        target_type: "args",
        target_value: "q",
        scope_path: "/search/basic",
        comment: "Learning mode: 12 events from 9 clients",
      }),
    );
    expect(policiesApi.createRuleExclusion).not.toHaveBeenCalled();
    expect(onExclusionCreated).toHaveBeenCalled();
  });

  it("links to the suggestion's events and shows the analysis result", async () => {
    vi.mocked(policiesApi.analyzeTuningSuggestions).mockResolvedValue({
      events_scanned: 340,
      created: 1,
      updated: 2,
      window_hours: 24,
    });
    renderCard();

    const link = await screen.findByRole("link", { name: "View events" });
    expect(link.getAttribute("href")).toMatch(/^\/logs\?rule_id=942100&date_from=/);
    await userEvent.click(screen.getByRole("button", { name: "Analyze now" }));

    expect(
      await screen.findByText(/Scanned 340 events from the last 24 hours: 1 new, 2 updated/),
    ).toBeInTheDocument();
    expect(policiesApi.listTuningSuggestions).toHaveBeenCalledTimes(2);
  });

  it("is read-only for viewers", async () => {
    renderCard(false);

    expect(await screen.findByText("942100")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Analyze now" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Review" })).not.toBeInTheDocument();
  });
});
