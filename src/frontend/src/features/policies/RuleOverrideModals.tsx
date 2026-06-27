import { type FormEvent, useState } from "react";

import { Modal } from "@/components/shared/Modal";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";
import {
  createRuleOverride,
  updateRuleOverride,
  deleteRuleOverride,
} from "@/features/policies/api";
import type {
  RuleOverride,
  RuleOverrideCreate,
  RuleOverrideUpdate,
} from "@/features/policies/types";
import { useAuth } from "@/hooks/use-auth";
import { ApiError } from "@/lib/api-client";

export type RuleOverrideModalState =
  | null
  | { type: "create"; policyId: number }
  | { type: "edit"; policyId: number; override: RuleOverride }
  | { type: "delete"; policyId: number; override: RuleOverride };

type RuleOverrideFormModalProps = {
  mode: "create" | "edit";
  policyId: number;
  override?: RuleOverride;
  onSuccess: () => void;
  onClose: () => void;
};

export function RuleOverrideFormModal({
  mode,
  policyId,
  override,
  onSuccess,
  onClose,
}: RuleOverrideFormModalProps) {
  const { accessToken } = useAuth();
  const [ruleId, setRuleId] = useState(String(override?.rule_id ?? ""));
  const [action, setAction] = useState<"enable" | "disable">(
    override?.action ?? "disable",
  );
  const [comment, setComment] = useState(override?.comment ?? "");
  const [submitting, setSubmitting] = useState(false);
  const [serverError, setServerError] = useState<string | null>(null);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    if (!accessToken) return;

    const parsedRuleId = Number(ruleId);
    if (!Number.isInteger(parsedRuleId) || parsedRuleId <= 0) {
      setServerError("Rule ID must be greater than 0");
      return;
    }

    setSubmitting(true);
    setServerError(null);

    const body: RuleOverrideCreate | RuleOverrideUpdate = {
      rule_id: parsedRuleId,
      action,
      comment: comment || null,
    };

    try {
      if (mode === "edit" && override) {
        await updateRuleOverride(accessToken, policyId, override.id, body);
      } else {
        await createRuleOverride(accessToken, policyId, body as RuleOverrideCreate);
      }
      onSuccess();
    } catch (err) {
      setServerError(
        err instanceof ApiError ? err.detail : "An unexpected error occurred",
      );
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <Modal
      title={mode === "create" ? "Add rule override" : "Edit rule override"}
      onClose={onClose}
      footer={
        <>
          <Button type="button" onClick={onClose} variant="outline">
            Cancel
          </Button>
          <Button
            type="submit"
            form="rule-override-form"
            disabled={submitting}
          >
            {submitting ? "Saving..." : "Save"}
          </Button>
        </>
      }
    >
      <form
        id="rule-override-form"
        onSubmit={(e) => void handleSubmit(e)}
        className="space-y-4"
      >
        {serverError && (
          <Alert
            variant="destructive"
            aria-live="assertive"
          >
            {serverError}
          </Alert>
        )}

        <div className="space-y-1.5">
          <Label htmlFor="rule-override-rule-id" className="text-foreground">
            Rule ID
          </Label>
          <Input
            id="rule-override-rule-id"
            type="number"
            required
            min={1}
            value={ruleId}
            onChange={(e) => setRuleId(e.target.value)}
            placeholder="942100"
          />
        </div>

        <div className="space-y-1.5">
          <Label htmlFor="rule-override-action" className="text-foreground">
            Action
          </Label>
          <Select
            id="rule-override-action"
            value={action}
            onChange={(e) => setAction(e.target.value as "enable" | "disable")}
          >
            <option value="enable">Enable</option>
            <option value="disable">Disable</option>
          </Select>
        </div>

        <div className="space-y-1.5">
          <Label htmlFor="rule-override-comment" className="text-foreground">
            Comment
          </Label>
          <Input
            id="rule-override-comment"
            type="text"
            value={comment}
            onChange={(e) => setComment(e.target.value)}
            placeholder="Optional"
          />
        </div>
      </form>
    </Modal>
  );
}

type DeleteRuleOverrideDialogProps = {
  policyId: number;
  override: RuleOverride;
  onSuccess: () => void;
  onClose: () => void;
};

export function DeleteRuleOverrideDialog({
  policyId,
  override,
  onSuccess,
  onClose,
}: DeleteRuleOverrideDialogProps) {
  const { accessToken } = useAuth();
  const [submitting, setSubmitting] = useState(false);
  const [serverError, setServerError] = useState<string | null>(null);

  async function handleDelete() {
    if (!accessToken) return;

    setSubmitting(true);
    setServerError(null);

    try {
      await deleteRuleOverride(accessToken, policyId, override.id);
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
      title="Delete rule override"
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
            {submitting ? "Deleting..." : "Delete"}
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
      <p className="text-sm text-fg">
        Are you sure you want to delete the override for rule{" "}
        <span className="font-semibold text-fg">{override.rule_id}</span>?
        This action cannot be undone.
      </p>
    </Modal>
  );
}
