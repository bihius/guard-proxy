import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { AuthContext } from "@/features/auth/auth-context.shared";
import type { AuthContextValue } from "@/features/auth/auth-context.types";
import * as bannedIpsApi from "@/features/banned-ips/api";

import { BannedIpsPage } from "./BannedIpsPage";

vi.mock("@/features/banned-ips/api");

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

const mockListResponse = {
  items: [
    {
      ip: "203.0.113.10",
      vhost_id: 1,
      domain: "app.example.com",
      gpc0: 12,
      ban_threshold: 10,
      banned: true,
      expires_in_seconds: 90,
    },
    {
      ip: "203.0.113.20",
      vhost_id: 2,
      domain: "api.example.com",
      gpc0: 4,
      ban_threshold: 10,
      banned: false,
      expires_in_seconds: 30,
    },
  ],
  total: 2,
};

const emptyListResponse = { items: [], total: 0 };

function renderPage(authOverrides: Partial<AuthContextValue> = {}) {
  return render(
    <AuthContext.Provider value={makeAuthContext(authOverrides)}>
      <BannedIpsPage />
    </AuthContext.Provider>,
  );
}

describe("BannedIpsPage", () => {
  it("shows loading state initially", () => {
    vi.mocked(bannedIpsApi.listBannedIps).mockReturnValue(new Promise(() => undefined));

    renderPage();
    expect(screen.getByText(/loading banned ips/i)).toBeInTheDocument();
  });

  it("renders only actively banned IPs, excluding merely-tracked entries", async () => {
    vi.mocked(bannedIpsApi.listBannedIps).mockResolvedValue(mockListResponse);

    renderPage();

    await waitFor(() => expect(screen.getByText("203.0.113.10")).toBeInTheDocument());
    expect(screen.getByText("app.example.com")).toBeInTheDocument();
    expect(screen.getByText("12 / 10")).toBeInTheDocument();
    expect(screen.queryByText("203.0.113.20")).not.toBeInTheDocument();
  });

  it("shows error state and retry button on failure", async () => {
    vi.mocked(bannedIpsApi.listBannedIps).mockRejectedValue(new Error("Network error"));

    renderPage();

    await waitFor(() =>
      expect(screen.getByText(/failed to load banned ips/i)).toBeInTheDocument(),
    );
    expect(screen.getByRole("button", { name: /retry/i })).toBeInTheDocument();
  });

  it("shows empty state when there are no banned IPs", async () => {
    vi.mocked(bannedIpsApi.listBannedIps).mockResolvedValue(emptyListResponse);

    renderPage();

    await waitFor(() => expect(screen.getByText(/no banned ips/i)).toBeInTheDocument());
  });

  it("admin sees the Unban action, viewer does not", async () => {
    vi.mocked(bannedIpsApi.listBannedIps).mockResolvedValue(mockListResponse);

    renderPage({ hasRole: vi.fn().mockReturnValue(false) });
    await waitFor(() => expect(screen.getByText("203.0.113.10")).toBeInTheDocument());
    expect(screen.queryByRole("button", { name: /unban/i })).not.toBeInTheDocument();
  });

  it("filters the list client-side by IP search", async () => {
    vi.mocked(bannedIpsApi.listBannedIps).mockResolvedValue(mockListResponse);

    renderPage();

    await waitFor(() => expect(screen.getByText("203.0.113.10")).toBeInTheDocument());
    await userEvent.type(screen.getByLabelText(/search banned ips/i), "999.999");

    await waitFor(() =>
      expect(screen.queryByText("203.0.113.10")).not.toBeInTheDocument(),
    );
    expect(screen.getByText(/no banned ips/i)).toBeInTheDocument();
  });

  it("unbanning an IP calls the API and refreshes the list", async () => {
    vi.mocked(bannedIpsApi.listBannedIps).mockResolvedValue(mockListResponse);
    vi.mocked(bannedIpsApi.unbanIp).mockResolvedValue({ ip: "203.0.113.10", cleared: 1 });

    renderPage();

    await waitFor(() => expect(screen.getByText("203.0.113.10")).toBeInTheDocument());
    const callsBeforeUnban = vi.mocked(bannedIpsApi.listBannedIps).mock.calls.length;
    await userEvent.click(screen.getByRole("button", { name: /unban/i }));

    const dialog = screen.getByRole("dialog");
    await userEvent.click(within(dialog).getByRole("button", { name: /^unban$/i }));

    await waitFor(() =>
      expect(bannedIpsApi.unbanIp).toHaveBeenCalledWith("test-token", "203.0.113.10"),
    );
    await waitFor(() =>
      expect(vi.mocked(bannedIpsApi.listBannedIps).mock.calls.length).toBe(
        callsBeforeUnban + 1,
      ),
    );
  });
});
