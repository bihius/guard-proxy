import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { ApiError } from "@/lib/api-client";

vi.mock("@/hooks/use-auth");
vi.mock("./api", () => ({
  applyConfig: vi.fn(),
}));

import { useAuth } from "@/hooks/use-auth";
import { applyConfig } from "./api";
import type { ConfigApplyResponse, RuntimeStatusResponse } from "./types";
import { ApplyConfigButton } from "./ApplyConfigButton";

const mockedUseAuth = vi.mocked(useAuth);
const mockedApplyConfig = vi.mocked(applyConfig);

function createAccessToken() {
  return "test-token";
}

function makeAuth(role: "admin" | "viewer") {
  return {
    hasRole: (r: string | string[]) =>
      Array.isArray(r) ? r.includes(role) : r === role,
    accessToken: createAccessToken(),
    user: null,
    role,
    isAuthenticated: true,
    isLoading: false,
    loginError: null,
    signIn: vi.fn(),
    signOut: vi.fn(),
    refreshCurrentUser: vi.fn(),
  };
}

const pendingStatus: RuntimeStatusResponse = {
  frontend_contract_version: "1",
  deployment_state: "deployed",
  generated_config: {
    can_generate: true,
    checksum: "new-checksum",
    generated_at: "2026-01-01T00:00:00Z",
    error: null,
  },
  latest_validation: null,
  latest_reload: {
    id: 1,
    operation_type: "reload",
    status: "success",
    config_checksum: "old-checksum",
    message: null,
    created_at: "2026-01-01T00:00:00Z",
  },
};

const noop = { data: pendingStatus, refresh: vi.fn() };

describe("ApplyConfigButton", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders the button for admin", () => {
    mockedUseAuth.mockReturnValue(makeAuth("admin"));
    render(<ApplyConfigButton runtimeStatus={noop} />);
    expect(screen.getByRole("button", { name: /apply config/i })).toBeInTheDocument();
  });

  it("returns null for viewer", () => {
    mockedUseAuth.mockReturnValue(makeAuth("viewer"));
    const { container } = render(<ApplyConfigButton runtimeStatus={noop} />);
    expect(container).toBeEmptyDOMElement();
  });

  it("returns null for admin when there are no pending changes", () => {
    mockedUseAuth.mockReturnValue(makeAuth("admin"));
    const upToDateStatus: RuntimeStatusResponse = {
      ...pendingStatus,
      latest_reload: {
        ...pendingStatus.latest_reload!,
        config_checksum: pendingStatus.generated_config.checksum,
      },
    };
    const { container } = render(
      <ApplyConfigButton runtimeStatus={{ data: upToDateStatus, refresh: vi.fn() }} />,
    );
    expect(container).toBeEmptyDOMElement();
  });

  it("returns null for admin when runtime status has not loaded yet", () => {
    mockedUseAuth.mockReturnValue(makeAuth("admin"));
    const { container } = render(
      <ApplyConfigButton runtimeStatus={{ data: null, refresh: vi.fn() }} />,
    );
    expect(container).toBeEmptyDOMElement();
  });

  it("disables the button while in-flight and re-enables after", async () => {
    mockedUseAuth.mockReturnValue(makeAuth("admin"));

    let resolveApply!: (v: ConfigApplyResponse) => void;
    mockedApplyConfig.mockReturnValueOnce(
      new Promise<ConfigApplyResponse>((res) => {
        resolveApply = res;
      }),
    );

    render(<ApplyConfigButton runtimeStatus={noop} />);
    const btn = screen.getByRole("button", { name: /apply config/i });
    fireEvent.click(btn);

    await waitFor(() => {
      expect(screen.getByRole("button")).toBeDisabled();
    });

    resolveApply({ status: "ok", correlation_id: "c1", checksum: "abc", message: "Done" });

    await waitFor(() => {
      expect(screen.getByRole("button")).not.toBeDisabled();
    });
  });

  it("calls refresh and onResult with success after apply", async () => {
    mockedUseAuth.mockReturnValue(makeAuth("admin"));
    const refreshMock = vi.fn();
    const onResult = vi.fn();

    mockedApplyConfig.mockResolvedValueOnce({
      status: "ok",
      correlation_id: "corr-1",
      checksum: "abc123",
      message: "Config applied successfully",
    });

    render(
      <ApplyConfigButton
        runtimeStatus={{ data: pendingStatus, refresh: refreshMock }}
        onResult={onResult}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: /apply config/i }));

    await waitFor(() => {
      expect(refreshMock).toHaveBeenCalledTimes(1);
      expect(onResult).toHaveBeenCalledWith({
        kind: "success",
        message: "Config applied successfully",
        correlationId: "corr-1",
      });
    });
  });

  it("calls onResult with error when apply fails", async () => {
    mockedUseAuth.mockReturnValue(makeAuth("admin"));
    const onResult = vi.fn();

    mockedApplyConfig.mockRejectedValueOnce(
      new ApiError(422, "Invalid config: syntax error"),
    );

    render(
      <ApplyConfigButton runtimeStatus={noop} onResult={onResult} />,
    );

    fireEvent.click(screen.getByRole("button", { name: /apply config/i }));

    await waitFor(() => {
      expect(onResult).toHaveBeenCalledWith({
        kind: "error",
        message: "Invalid config: syntax error",
      });
    });
  });

  it("ignores duplicate clicks while in-flight", async () => {
    mockedUseAuth.mockReturnValue(makeAuth("admin"));
    let resolveApply!: (v: ConfigApplyResponse) => void;
    mockedApplyConfig.mockReturnValueOnce(
      new Promise<ConfigApplyResponse>((res) => {
        resolveApply = res;
      }),
    );

    render(<ApplyConfigButton runtimeStatus={noop} />);
    const btn = screen.getByRole("button", { name: /apply config/i });
    fireEvent.click(btn);

    await waitFor(() => expect(btn).toBeDisabled());

    fireEvent.click(btn);
    fireEvent.click(btn);

    resolveApply({ status: "ok", correlation_id: "c1", checksum: "abc", message: "Done" });

    await waitFor(() => expect(btn).not.toBeDisabled());
    expect(mockedApplyConfig).toHaveBeenCalledTimes(1);
  });
});
