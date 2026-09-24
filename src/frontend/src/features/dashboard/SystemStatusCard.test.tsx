import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import type { RuntimeStatusResponse } from "@/features/runtime/types";

import { SystemStatusCard } from "./SystemStatusCard";

function renderCard(reloadStatus: "success" | "failed") {
  const data = {
    frontend_contract_version: "1",
    deployment_state: reloadStatus === "success" ? "deployed" : "failed",
    generated_config: {
      can_generate: true,
      checksum: "abc123def456789",
      generated_at: "2026-07-29T10:00:00Z",
      error: null,
    },
    latest_validation: null,
    // A failed reload is rolled back but still stores the candidate's checksum,
    // so generated and "reloaded" checksums match in both cases.
    latest_reload: {
      id: 1,
      operation_type: "reload",
      status: reloadStatus,
      config_checksum: "abc123def456789",
      message: reloadStatus === "failed" ? "reload rejected" : null,
      created_at: "2026-07-29T10:00:00Z",
    },
  } as RuntimeStatusResponse;

  render(
    <SystemStatusCard
      status={{ data, isLoading: false, error: null, refresh: vi.fn() }}
      overview={null}
    />,
  );
}

describe("SystemStatusCard", () => {
  it("treats a failed reload as not live even when the checksums match", () => {
    renderCard("failed");

    expect(screen.getByText(/have not been applied yet/i)).toBeInTheDocument();
    expect(screen.getByText("Last attempted config")).toBeInTheDocument();
    expect(screen.queryByText("Running config")).not.toBeInTheDocument();
  });

  it("shows no pending warning after a successful reload of the generated config", () => {
    renderCard("success");

    expect(screen.queryByText(/have not been applied yet/i)).not.toBeInTheDocument();
    expect(screen.getByText("Running config")).toBeInTheDocument();
  });
});
