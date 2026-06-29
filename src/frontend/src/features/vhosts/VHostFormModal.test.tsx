import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { AuthContext } from "@/features/auth/auth-context.shared";
import type { AuthContextValue } from "@/features/auth/auth-context.types";
import { ApiError } from "@/lib/api-client";

import * as api from "./api";
import { VHostFormModal } from "./VHostFormModal";
import type { Policy } from "./types";

vi.mock("./api");

const policies: Policy[] = [
  { id: 1, name: "Default" },
  { id: 2, name: "Strict" },
];

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

function renderCreateModal(onSuccess = vi.fn(), onClose = vi.fn()) {
  return render(
    <AuthContext.Provider value={makeAuthContext()}>
      <VHostFormModal mode="create" policies={policies} onSuccess={onSuccess} onClose={onClose} />
    </AuthContext.Provider>,
  );
}

describe("VHostFormModal (create)", () => {
  it("submits create payload with filled fields", async () => {
    vi.mocked(api.createVHost).mockResolvedValue({
      id: 1,
      domain: "new.example.com",
      backend_url: "https://new.internal",
      backends: [
        {
          id: 1,
          vhost_id: 1,
          url: "https://new.internal",
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
      ssl_enabled: false, ssl_provider: "none" as const, ssl_expires_at: null,
      is_active: true,
      policy_id: null,
      created_by: 1,
      created_at: "2026-01-01T00:00:00Z",
      updated_at: "2026-01-01T00:00:00Z",
    });

    const onSuccess = vi.fn();
    renderCreateModal(onSuccess);

    await userEvent.type(screen.getByLabelText("Domain"), "new.example.com");
    await userEvent.type(screen.getByLabelText("Backend URL"), "https://new.internal");
    await userEvent.click(screen.getByRole("button", { name: "Create" }));

    await waitFor(() => expect(onSuccess).toHaveBeenCalledOnce());
    expect(api.createVHost).toHaveBeenCalledWith(
      "test-token",
      expect.objectContaining({
        domain: "new.example.com",
        backend_url: "https://new.internal",
        backends: [
          expect.objectContaining({
            url: "https://new.internal",
            health_check_enabled: true,
            health_check_path: "/",
          }),
        ],
      }),
    );
  });

  it("shows server error detail on rejection", async () => {
    vi.mocked(api.createVHost).mockRejectedValue(
      new ApiError(409, "Domain already exists"),
    );

    renderCreateModal();

    await userEvent.type(screen.getByLabelText("Domain"), "dup.example.com");
    await userEvent.type(screen.getByLabelText("Backend URL"), "https://dup.internal");
    await userEvent.click(screen.getByRole("button", { name: "Create" }));

    await waitFor(() =>
      expect(screen.getByRole("alert")).toHaveTextContent("Domain already exists"),
    );
  });
});
