import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import type { RuntimeStatusResponse } from "./types";
import { RuntimeStatusCard } from "./RuntimeStatusCard";

function makeStatus(
  overrides: Partial<{
    data: RuntimeStatusResponse | null;
    isLoading: boolean;
    error: string | null;
    refresh: () => void;
  }> = {},
) {
  return {
    data: null,
    isLoading: false,
    error: null,
    refresh: () => undefined,
    ...overrides,
  };
}

function makeRuntimeData(
  overrides: Partial<RuntimeStatusResponse> = {},
): RuntimeStatusResponse {
  return {
    frontend_contract_version: "1",
    deployment_state: "deployed",
    generated_config: {
      can_generate: true,
      checksum: "abcdef123456",
      generated_at: "2026-05-01T12:00:00Z",
      error: null,
    },
    latest_validation: null,
    latest_reload: null,
    ...overrides,
  };
}

describe("RuntimeStatusCard", () => {
  it("shows loading state", () => {
    render(<RuntimeStatusCard status={makeStatus({ isLoading: true })} />);
    expect(screen.getByText(/loading runtime status/i)).toBeInTheDocument();
  });

  it("shows error state", () => {
    render(
      <RuntimeStatusCard
        status={makeStatus({ error: "Network error" })}
      />,
    );
    expect(screen.getByText("Network error")).toBeInTheDocument();
  });

  it("renders deployed badge and checksum", () => {
    render(
      <RuntimeStatusCard
        status={makeStatus({ data: makeRuntimeData() })}
      />,
    );
    expect(screen.getByText("Deployed")).toBeInTheDocument();
    expect(screen.getByText("abcdef123456".slice(0, 12))).toBeInTheDocument();
  });

  it("renders never_deployed badge", () => {
    render(
      <RuntimeStatusCard
        status={makeStatus({
          data: makeRuntimeData({ deployment_state: "never_deployed" }),
        })}
      />,
    );
    expect(screen.getByText("Never deployed")).toBeInTheDocument();
  });

  it("renders failed badge", () => {
    render(
      <RuntimeStatusCard
        status={makeStatus({
          data: makeRuntimeData({ deployment_state: "failed" }),
        })}
      />,
    );
    expect(screen.getByText("Failed")).toBeInTheDocument();
  });

  it("shows reload failure message when latest_reload status is failed", () => {
    render(
      <RuntimeStatusCard
        status={makeStatus({
          data: makeRuntimeData({
            latest_reload: {
              id: 1,
              operation_type: "reload",
              status: "failed",
              config_checksum: "deadbeef1234",
              message: "HAProxy failed to reload: syntax error on line 42",
              created_at: "2026-05-01T13:00:00Z",
            },
          }),
        })}
      />,
    );
    expect(
      screen.getByText(/HAProxy failed to reload/),
    ).toBeInTheDocument();
  });

  it("shows dash when no latest_reload", () => {
    render(
      <RuntimeStatusCard
        status={makeStatus({ data: makeRuntimeData({ latest_reload: null }) })}
      />,
    );
    expect(screen.getByText("Last reload")).toBeInTheDocument();
  });
});
