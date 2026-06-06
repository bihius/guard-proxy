import { useState } from "react";

import { Modal } from "@/components/shared/Modal";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { useAuth } from "@/hooks/use-auth";
import { ApiError } from "@/lib/api-client";

import { deleteVHost } from "./api";
import type { VHost } from "./types";

type DeleteVHostDialogProps = {
  vhost: VHost;
  onSuccess: () => void;
  onClose: () => void;
};

export function DeleteVHostDialog({ vhost, onSuccess, onClose }: DeleteVHostDialogProps) {
  const { accessToken } = useAuth();
  const [submitting, setSubmitting] = useState(false);
  const [serverError, setServerError] = useState<string | null>(null);

  async function handleDelete() {
    if (!accessToken) return;
    setSubmitting(true);
    setServerError(null);
    try {
      await deleteVHost(accessToken, vhost.id);
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
      title="Delete virtual host"
      onClose={onClose}
      footer={
        <>
          <Button type="button" onClick={onClose} variant="outline">
            Cancel
          </Button>
          <Button
            type="button"
            disabled={submitting}
            onClick={() => void handleDelete()}
            variant="destructive"
          >
            {submitting ? "Deleting…" : "Delete"}
          </Button>
        </>
      }
    >
      {serverError && (
        <Alert
          variant="destructive"
          aria-live="assertive"
        >
          {serverError}
        </Alert>
      )}
      <p className="text-sm text-foreground">
        Are you sure you want to delete{" "}
        <span className="font-semibold text-foreground">{vhost.domain}</span>?
        This action cannot be undone.
      </p>
    </Modal>
  );
}
