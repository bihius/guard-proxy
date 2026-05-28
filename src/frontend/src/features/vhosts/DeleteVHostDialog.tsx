import { useState } from "react";

import { Modal } from "@/components/shared/Modal";
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
          <button type="button" onClick={onClose} className="btn-ghost px-4 py-2 text-sm">
            Cancel
          </button>
          <button
            type="button"
            disabled={submitting}
            onClick={() => void handleDelete()}
            className="rounded-[var(--radius-md)] bg-error px-4 py-2 text-sm font-semibold text-white transition hover:opacity-90 disabled:opacity-50"
          >
            {submitting ? "Deleting…" : "Delete"}
          </button>
        </>
      }
    >
      {serverError && (
        <div
          role="alert"
          aria-live="assertive"
          className="rounded-[var(--radius-md)] bg-error-soft px-4 py-3 text-sm font-medium text-error"
        >
          {serverError}
        </div>
      )}
      <p className="text-sm text-fg">
        Are you sure you want to delete{" "}
        <span className="font-semibold text-fg">{vhost.domain}</span>?
        This action cannot be undone.
      </p>
    </Modal>
  );
}
