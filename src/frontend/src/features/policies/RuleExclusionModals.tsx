import { type FormEvent, useState } from "react";

import { Modal } from "@/components/shared/Modal";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";
import {
  createRuleExclusion,
  updateRuleExclusion,
  deleteRuleExclusion,
} from "@/features/policies/api";
import type {
  RuleExclusion,
  RuleExclusionCreate,
  RuleExclusionTargetType,
  RuleExclusionUpdate,
} from "@/features/policies/types";
import { useAuth } from "@/hooks/use-auth";
import { ApiError } from "@/lib/api-client";

export type RuleExclusionModalState =
  | null
  | { type: "create"; policyId: number }
  | { type: "edit"; policyId: number; exclusion: RuleExclusion }
  | { type: "delete"; policyId: number; exclusion: RuleExclusion };

const TARGET_TYPE_OPTIONS: { value: RuleExclusionTargetType; label: string }[] = [
  { value: "request_uri", label: "Request URI" },
  { value: "args", label: "Args" },
  { value: "args_names", label: "Args names" },
  { value: "request_headers", label: "Request headers" },
];

type RuleExclusionFormModalProps = {
  mode: "create" | "edit";
  policyId: number;
  exclusion?: RuleExclusion;
  onSuccess: () => void;
  onClose: () => void;
};

export function RuleExclusionFormModal({
  mode,
  policyId,
  exclusion,
  onSuccess,
  onClose,
}: RuleExclusionFormModalProps) {
  const { accessToken } = useAuth();
  const [ruleId, setRuleId] = useState(String(exclusion?.rule_id ?? ""));
  const [targetType, setTargetType] = useState<RuleExclusionTargetType>(
    exclusion?.target_type ?? "args",
  );
  const [targetValue, setTargetValue] = useState(exclusion?.target_value ?? "");
  const [scopePath, setScopePath] = useState(exclusion?.scope_path ?? "");
  const [comment, setComment] = useState(exclusion?.comment ?? "");
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

    if (!targetValue.trim()) {
      setServerError("Target value must not be blank");
      return;
    }

    setSubmitting(true);
    setServerError(null);

    const body: RuleExclusionCreate | RuleExclusionUpdate = {
      rule_id: parsedRuleId,
      target_type: targetType,
      target_value: targetValue,
      scope_path: scopePath || null,
      comment: comment || null,
    };

    try {
      if (mode === "edit" && exclusion) {
        await updateRuleExclusion(accessToken, policyId, exclusion.id, body);
      } else {
        await createRuleExclusion(accessToken, policyId, body as RuleExclusionCreate);
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
      title={mode === "create" ? "Add rule exclusion" : "Edit rule exclusion"}
      onClose={onClose}
      footer={
        <>
          <Button type="button" onClick={onClose} variant="outline">
            Cancel
          </Button>
          <Button
            type="submit"
            form="rule-exclusion-form"
            disabled={submitting}
          >
            {submitting ? "Saving..." : "Save"}
          </Button>
        </>
      }
    >
      <form
        id="rule-exclusion-form"
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
          <Label htmlFor="rule-exclusion-rule-id" className="text-foreground">
            Rule ID
          </Label>
          <Input
            id="rule-exclusion-rule-id"
            type="number"
            required
            min={1}
            value={ruleId}
            onChange={(e) => setRuleId(e.target.value)}
            placeholder="942100"
          />
        </div>

        <div className="space-y-1.5">
          <Label htmlFor="rule-exclusion-target-type" className="text-foreground">
            Target type
          </Label>
          <Select
            id="rule-exclusion-target-type"
            value={targetType}
            onChange={(e) => setTargetType(e.target.value as RuleExclusionTargetType)}
          >
            {TARGET_TYPE_OPTIONS.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </Select>
        </div>

        <div className="space-y-1.5">
          <Label htmlFor="rule-exclusion-target-value" className="text-foreground">
            Target value
          </Label>
          <Input
            id="rule-exclusion-target-value"
            type="text"
            required
            value={targetValue}
            onChange={(e) => setTargetValue(e.target.value)}
            placeholder="token"
          />
        </div>

        <div className="space-y-1.5">
          <Label htmlFor="rule-exclusion-scope-path" className="text-foreground">
            Scope path
          </Label>
          <Input
            id="rule-exclusion-scope-path"
            type="text"
            value={scopePath}
            onChange={(e) => setScopePath(e.target.value)}
            placeholder="Optional, e.g. /api/login"
          />
        </div>

        <div className="space-y-1.5">
          <Label htmlFor="rule-exclusion-comment" className="text-foreground">
            Comment
          </Label>
          <Input
            id="rule-exclusion-comment"
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

type DeleteRuleExclusionDialogProps = {
  policyId: number;
  exclusion: RuleExclusion;
  onSuccess: () => void;
  onClose: () => void;
};

export function DeleteRuleExclusionDialog({
  policyId,
  exclusion,
  onSuccess,
  onClose,
}: DeleteRuleExclusionDialogProps) {
  const { accessToken } = useAuth();
  const [submitting, setSubmitting] = useState(false);
  const [serverError, setServerError] = useState<string | null>(null);

  async function handleDelete() {
    if (!accessToken) return;

    setSubmitting(true);
    setServerError(null);

    try {
      await deleteRuleExclusion(accessToken, policyId, exclusion.id);
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
      title="Delete rule exclusion"
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
        Are you sure you want to delete the exclusion for rule{" "}
        <span className="font-semibold text-fg">{exclusion.rule_id}</span>?
        This action cannot be undone.
      </p>
    </Modal>
  );
}
