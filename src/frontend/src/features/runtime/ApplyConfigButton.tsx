import { useState } from "react";

import { useAuth } from "@/hooks/use-auth";
import { ApiError } from "@/lib/api-client";

import { applyConfig } from "./api";

type ApplyResult = {
  kind: "success" | "error";
  message: string;
  correlationId?: string;
};

type ApplyConfigButtonProps = {
  runtimeStatus: { refresh: () => void };
  onResult?: (result: ApplyResult) => void;
};

export function ApplyConfigButton({
  runtimeStatus,
  onResult,
}: ApplyConfigButtonProps) {
  const { hasRole, accessToken } = useAuth();
  const [isApplying, setIsApplying] = useState(false);

  if (!hasRole("admin")) return null;

  async function handleClick() {
    if (isApplying || !accessToken) return;

    setIsApplying(true);
    try {
      const result = await applyConfig(accessToken);
      const applyResult: ApplyResult = {
        kind: "success",
        message: result.message,
        correlationId: result.correlation_id,
      };
      onResult?.(applyResult);
      runtimeStatus.refresh();
    } catch (err) {
      const message =
        err instanceof ApiError ? err.detail : "Apply failed unexpectedly";
      onResult?.({ kind: "error", message });
    } finally {
      setIsApplying(false);
    }
  }

  return (
    <button
      type="button"
      disabled={isApplying}
      onClick={() => void handleClick()}
      className="inline-flex items-center gap-2 rounded-[var(--radius-md)] bg-accent px-4 py-2 text-sm font-semibold text-white shadow-sm transition-opacity hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-50"
    >
      {isApplying ? (
        <>
          <span className="h-3.5 w-3.5 animate-spin rounded-full border-2 border-white/40 border-t-white" />
          Applying…
        </>
      ) : (
        "Apply config"
      )}
    </button>
  );
}

export type { ApplyResult };
