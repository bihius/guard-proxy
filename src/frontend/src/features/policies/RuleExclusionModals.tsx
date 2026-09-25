import { type FormEvent, type ReactNode, useState } from "react";

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
  RuleExclusionSuggestion,
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

/** `takesKey`: the Coraza variable is a collection, so the exclusion names one member. */
const TARGET_TYPES: Record<RuleExclusionTargetType, { label: string; takesKey: boolean }> = {
  args: { label: "Args", takesKey: true },
  args_names: { label: "Args names", takesKey: true },
  request_headers: { label: "Request headers", takesKey: true },
  request_headers_names: { label: "Request header names", takesKey: true },
  request_cookies: { label: "Request cookies", takesKey: true },
  request_cookies_names: { label: "Request cookie names", takesKey: true },
  request_uri: { label: "Request URI", takesKey: false },
  request_uri_raw: { label: "Request URI (raw)", takesKey: false },
  request_filename: { label: "Request filename (path)", takesKey: false },
};

type RuleExclusionFormModalProps = {
  mode: "create" | "edit";
  policyId: number;
  exclusion?: RuleExclusion;
  /** Create mode only: pre-fill the form, e.g. from a WAF event. */
  suggestion?: RuleExclusionSuggestion;
  /** Shown above the fields, e.g. to explain where the pre-filled values came from. */
  intro?: ReactNode;
  onSuccess: () => void;
  onClose: () => void;
};

export function RuleExclusionFormModal({
  mode,
  policyId,
  exclusion,
  suggestion,
  intro,
  onSuccess,
  onClose,
}: RuleExclusionFormModalProps) {
  const { accessToken } = useAuth();
  const initial = exclusion ?? suggestion;
  const [ruleId, setRuleId] = useState(String(initial?.rule_id ?? ""));
  const [targetType, setTargetType] = useState<RuleExclusionTargetType>(
    initial?.target_type ?? "args",
  );
  const [targetValue, setTargetValue] = useState(initial?.target_value ?? "");
  const [scopePath, setScopePath] = useState(initial?.scope_path ?? "");
  const [comment, setComment] = useState(initial?.comment ?? "");
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

    const takesKey = TARGET_TYPES[targetType].takesKey;
    if (takesKey && !targetValue.trim()) {
      setServerError("Target value must not be blank");
      return;
    }

    setSubmitting(true);
    setServerError(null);

    const body: RuleExclusionCreate | RuleExclusionUpdate = {
      rule_id: parsedRuleId,
      target_type: targetType,
      target_value: takesKey ? targetValue : null,
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
        {intro}
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
            {Object.entries(TARGET_TYPES).map(([value, { label }]) => (
              <option key={value} value={value}>
                {label}
              </option>
            ))}
          </Select>
        </div>

        {TARGET_TYPES[targetType].takesKey && (
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
        )}

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
