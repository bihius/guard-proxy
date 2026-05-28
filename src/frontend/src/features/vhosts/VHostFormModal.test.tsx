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
      description: null,
      ssl_enabled: false,
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
