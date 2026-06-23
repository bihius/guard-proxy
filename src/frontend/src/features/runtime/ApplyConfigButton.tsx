import { useState } from "react";
import { UploadCloud } from "lucide-react";

import { Button } from "@/components/ui/button";
import { useAuth } from "@/hooks/use-auth";
import { ApiError } from "@/lib/api-client";

import { applyConfig } from "./api";
import type { RuntimeStatusResponse } from "./types";

type ApplyResult = {
  kind: "success" | "error";
  message: string;
  correlationId?: string;
};

type ApplyConfigButtonProps = {
  runtimeStatus: {
    data: RuntimeStatusResponse | null;
    refresh: () => void;
  };
  onResult?: (result: ApplyResult) => void;
};

export function ApplyConfigButton({
  runtimeStatus,
  onResult,
}: ApplyConfigButtonProps) {
  const { hasRole, accessToken } = useAuth();
  const [isApplying, setIsApplying] = useState(false);

  const data = runtimeStatus.data;
  const hasPendingChanges =
    !!data &&
    !!data.generated_config.checksum &&
    data.generated_config.checksum !== data.latest_reload?.config_checksum;

  if (!hasRole("admin") || !hasPendingChanges) return null;

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
    <Button
      type="button"
      disabled={isApplying}
      onClick={() => void handleClick()}
    >
      {isApplying ? (
        <>
          <span className="h-3.5 w-3.5 animate-spin rounded-full border-2 border-primary-foreground/40 border-t-primary-foreground" />
          Applying…
        </>
      ) : (
        <>
          <UploadCloud />
          Apply config
        </>
      )}
    </Button>
  );
}

export type { ApplyResult };
