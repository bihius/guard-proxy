import { useState } from "react";

import { Modal } from "@/components/shared/Modal";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { useAuth } from "@/hooks/use-auth";
import { ApiError } from "@/lib/api-client";

import { deletePolicy } from "./api";
import type { Policy } from "./types";

type DeletePolicyDialogProps = {
  policy: Policy;
  onSuccess: () => void;
  onClose: () => void;
};

export function DeletePolicyDialog({ policy, onSuccess, onClose }: DeletePolicyDialogProps) {
  const { accessToken } = useAuth();
  const [submitting, setSubmitting] = useState(false);
  const [serverError, setServerError] = useState<string | null>(null);

  async function handleDelete() {
    if (!accessToken) return;
    setSubmitting(true);
    setServerError(null);
    try {
      await deletePolicy(accessToken, policy.id);
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
      title="Delete policy"
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
        <span className="font-semibold text-foreground">{policy.name}</span>?
        This action cannot be undone.
      </p>
    </Modal>
  );
}
