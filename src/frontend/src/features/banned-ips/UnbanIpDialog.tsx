import { useState } from "react";

import { Modal } from "@/components/shared/Modal";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { useAuth } from "@/hooks/use-auth";
import { ApiError } from "@/lib/api-client";

import { unbanIp } from "./api";
import type { BannedIp } from "./types";

type UnbanIpDialogProps = {
  bannedIp: BannedIp;
  onSuccess: () => void;
  onClose: () => void;
};

export function UnbanIpDialog({ bannedIp, onSuccess, onClose }: UnbanIpDialogProps) {
  const { accessToken } = useAuth();
  const [submitting, setSubmitting] = useState(false);
  const [serverError, setServerError] = useState<string | null>(null);

  async function handleUnban() {
    if (!accessToken) return;
    setSubmitting(true);
    setServerError(null);
    try {
      await unbanIp(accessToken, bannedIp.ip);
      onSuccess();
    } catch (err) {
      setServerError(
        err instanceof ApiError ? err.detail : "An unexpected error occurred",
      );
      setSubmitting(false);
    }
  }

  return (
    <Modal
      title="Unban IP address"
      onClose={onClose}
      footer={
        <>
          <Button type="button" onClick={onClose} variant="outline">
            Cancel
          </Button>
          <Button
            type="button"
            disabled={submitting}
            onClick={() => void handleUnban()}
            variant="destructive"
          >
            {submitting ? "Unbanning…" : "Unban"}
          </Button>
        </>
      }
    >
      {serverError && (
        <Alert variant="destructive" aria-live="assertive">
          {serverError}
        </Alert>
      )}
      <p className="text-sm text-foreground">
        Are you sure you want to unban{" "}
        <span className="font-mono font-semibold text-foreground">{bannedIp.ip}</span>{" "}
        across <span className="font-semibold text-foreground">all virtual hosts</span>?
        This clears the address from every active ban table, not just{" "}
        <span className="font-semibold text-foreground">{bannedIp.domain}</span>.
      </p>
    </Modal>
  );
}
