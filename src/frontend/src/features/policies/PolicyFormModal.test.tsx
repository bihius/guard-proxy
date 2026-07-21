import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { AuthContext } from "@/features/auth/auth-context.shared";
import type { AuthContextValue } from "@/features/auth/auth-context.types";

import * as api from "./api";
import { PolicyFormModal } from "./PolicyFormModal";
import type { Policy } from "./types";

vi.mock("./api");

function makeAuthContext(overrides: Partial<AuthContextValue> = {}): AuthContextValue {
  return {
    user: null,
    role: null,
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

const editPolicy: Policy = {
  id: 1,
  name: "Default WAF",
  description: null,
  paranoia_level: 2,
  inbound_anomaly_threshold: 5,
  outbound_anomaly_threshold: 4,
  enforcement_mode: "block",
  is_active: true,
  ddos_protection_enabled: false,
  rate_limit_requests: 100,
  rate_limit_window_seconds: 10,
  max_connections_per_ip: 20,
  created_by: 1,
  created_at: "2026-01-01T00:00:00Z",
  updated_at: "2026-01-01T00:00:00Z",
};

function renderCreateModal(onSuccess = vi.fn(), onClose = vi.fn()) {
  return render(
    <AuthContext.Provider value={makeAuthContext()}>
      <PolicyFormModal mode="create" onSuccess={onSuccess} onClose={onClose} />
    </AuthContext.Provider>,
  );
}

function renderEditModal(onSuccess = vi.fn(), onClose = vi.fn()) {
  return render(
    <AuthContext.Provider value={makeAuthContext()}>
      <PolicyFormModal mode="edit" policy={editPolicy} onSuccess={onSuccess} onClose={onClose} />
    </AuthContext.Provider>,
  );
}

describe("PolicyFormModal DDoS protection fields", () => {
  it("disables the numeric fields until DDoS protection is enabled", () => {
    renderCreateModal();

    expect(screen.getByLabelText("Rate limit (requests)")).toBeDisabled();
    expect(screen.getByLabelText("Rate limit window (seconds)")).toBeDisabled();
    expect(screen.getByLabelText("Max connections per IP")).toBeDisabled();
  });

  it("enables the numeric fields once the toggle is checked", async () => {
    renderCreateModal();

    await userEvent.click(screen.getByText("DDoS protection"));

    expect(screen.getByLabelText("Rate limit (requests)")).toBeEnabled();
    expect(screen.getByLabelText("Rate limit window (seconds)")).toBeEnabled();
    expect(screen.getByLabelText("Max connections per IP")).toBeEnabled();
  });

  it("submits DDoS fields on create", async () => {
    vi.mocked(api.createPolicy).mockResolvedValue({ ...editPolicy, id: 2 });

    const onSuccess = vi.fn();
    renderCreateModal(onSuccess);

    await userEvent.type(screen.getByLabelText("Name"), "Hardened");
    await userEvent.click(screen.getByText("DDoS protection"));

    const rateLimitInput = screen.getByLabelText("Rate limit (requests)");
    await userEvent.clear(rateLimitInput);
    await userEvent.type(rateLimitInput, "50");

    await userEvent.click(screen.getByRole("button", { name: "Create" }));

    await waitFor(() => expect(onSuccess).toHaveBeenCalledOnce());
    expect(api.createPolicy).toHaveBeenCalledWith(
      "test-token",
      expect.objectContaining({
        ddos_protection_enabled: true,
        rate_limit_requests: 50,
        rate_limit_window_seconds: 10,
        max_connections_per_ip: 20,
      }),
    );
  });

  it("submits DDoS fields on update", async () => {
    vi.mocked(api.updatePolicy).mockResolvedValue(editPolicy);

    const onSuccess = vi.fn();
    renderEditModal(onSuccess);

    await userEvent.click(screen.getByText("DDoS protection"));
    await userEvent.click(screen.getByRole("button", { name: "Save" }));

    await waitFor(() => expect(onSuccess).toHaveBeenCalledOnce());
    expect(api.updatePolicy).toHaveBeenCalledWith(
      "test-token",
      editPolicy.id,
      expect.objectContaining({
        ddos_protection_enabled: true,
        rate_limit_requests: 100,
        rate_limit_window_seconds: 10,
        max_connections_per_ip: 20,
      }),
    );
  });
});
