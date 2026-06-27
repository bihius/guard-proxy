import { type FormEvent, useState } from "react";

import { Modal } from "@/components/shared/Modal";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";
import {
  createCustomRule,
  updateCustomRule,
  deleteCustomRule,
} from "@/features/policies/api";
import type {
  CustomRule,
  CustomRuleCreate,
  CustomRuleOperator,
  CustomRulePhase,
  CustomRuleUpdate,
} from "@/features/policies/types";
import { CUSTOM_RULE_ID_MAX, CUSTOM_RULE_ID_MIN } from "@/features/policies/types";
import { useAuth } from "@/hooks/use-auth";
import { ApiError } from "@/lib/api-client";

export type CustomRuleModalState =
  | null
  | { type: "create"; policyId: number }
  | { type: "edit"; policyId: number; rule: CustomRule }
  | { type: "delete"; policyId: number; rule: CustomRule };

const PHASE_OPTIONS: { value: CustomRulePhase; label: string }[] = [
  { value: "request_headers", label: "Request headers" },
  { value: "request_body", label: "Request body" },
  { value: "response_headers", label: "Response headers" },
  { value: "response_body", label: "Response body" },
  { value: "logging", label: "Logging" },
];

const OPERATOR_OPTIONS: { value: CustomRuleOperator; label: string }[] = [
  { value: "rx", label: "rx (regex)" },
  { value: "streq", label: "streq" },
  { value: "contains", label: "contains" },
  { value: "begins_with", label: "begins_with" },
  { value: "ends_with", label: "ends_with" },
  { value: "eq", label: "eq" },
  { value: "ge", label: "ge" },
  { value: "gt", label: "gt" },
  { value: "le", label: "le" },
  { value: "lt", label: "lt" },
  { value: "pm", label: "pm" },
  { value: "within", label: "within" },
  { value: "ip_match", label: "ip_match" },
];

type CustomRuleFormModalProps = {
  mode: "create" | "edit";
  policyId: number;
  rule?: CustomRule;
  onSuccess: () => void;
  onClose: () => void;
};

export function CustomRuleFormModal({
  mode,
  policyId,
  rule,
  onSuccess,
  onClose,
}: CustomRuleFormModalProps) {
  const { accessToken } = useAuth();
  const [ruleId, setRuleId] = useState(String(rule?.rule_id ?? ""));
  const [phase, setPhase] = useState<CustomRulePhase>(
    rule?.phase ?? "request_headers",
  );
  const [variables, setVariables] = useState(rule?.variables ?? "");
  const [operator, setOperator] = useState<CustomRuleOperator>(rule?.operator ?? "rx");
  const [operatorArgument, setOperatorArgument] = useState(
    rule?.operator_argument ?? "",
  );
  const [actions, setActions] = useState(rule?.actions ?? "");
  const [comment, setComment] = useState(rule?.comment ?? "");
  const [isActive, setIsActive] = useState(rule?.is_active ?? true);
  const [submitting, setSubmitting] = useState(false);
  const [serverError, setServerError] = useState<string | null>(null);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    if (!accessToken) return;

    const parsedRuleId = Number(ruleId);
    if (
      !Number.isInteger(parsedRuleId) ||
      parsedRuleId < CUSTOM_RULE_ID_MIN ||
      parsedRuleId > CUSTOM_RULE_ID_MAX
    ) {
      setServerError(
        `Rule ID must be between ${CUSTOM_RULE_ID_MIN} and ${CUSTOM_RULE_ID_MAX}`,
      );
      return;
    }

    if (!variables.trim() || !operatorArgument.trim() || !actions.trim()) {
      setServerError("Variables, operator argument, and actions must not be blank");
      return;
    }

    setSubmitting(true);
    setServerError(null);

    const body: CustomRuleCreate | CustomRuleUpdate = {
      rule_id: parsedRuleId,
      phase,
      variables,
      operator,
      operator_argument: operatorArgument,
      actions,
      comment: comment || null,
      is_active: isActive,
    };

    try {
      if (mode === "edit" && rule) {
        await updateCustomRule(accessToken, policyId, rule.id, body);
      } else {
        await createCustomRule(accessToken, policyId, body as CustomRuleCreate);
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
      title={mode === "create" ? "Add custom rule" : "Edit custom rule"}
      onClose={onClose}
      footer={
        <>
          <Button type="button" onClick={onClose} variant="outline">
            Cancel
          </Button>
          <Button
            type="submit"
            form="custom-rule-form"
            disabled={submitting}
          >
            {submitting ? "Saving..." : "Save"}
          </Button>
        </>
      }
    >
      <form
        id="custom-rule-form"
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
          <Label htmlFor="custom-rule-rule-id" className="text-foreground">
            Rule ID
          </Label>
          <Input
            id="custom-rule-rule-id"
            type="number"
            required
            value={ruleId}
            onChange={(e) => setRuleId(e.target.value)}
            placeholder={String(CUSTOM_RULE_ID_MIN + 1)}
          />
          <p className="text-xs text-fg-subtle">
            Must be between {CUSTOM_RULE_ID_MIN} and {CUSTOM_RULE_ID_MAX} to avoid
            colliding with OWASP CRS rule IDs.
          </p>
        </div>

        <div className="space-y-1.5">
          <Label htmlFor="custom-rule-phase" className="text-foreground">
            Phase
          </Label>
          <Select
            id="custom-rule-phase"
            value={phase}
            onChange={(e) => setPhase(e.target.value as CustomRulePhase)}
          >
            {PHASE_OPTIONS.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </Select>
        </div>

        <div className="space-y-1.5">
          <Label htmlFor="custom-rule-variables" className="text-foreground">
            Variables
          </Label>
          <Input
            id="custom-rule-variables"
            type="text"
            required
            value={variables}
            onChange={(e) => setVariables(e.target.value)}
            placeholder="ARGS|REQUEST_HEADERS:User-Agent"
          />
        </div>

        <div className="space-y-1.5">
          <Label htmlFor="custom-rule-operator" className="text-foreground">
            Operator
          </Label>
          <Select
            id="custom-rule-operator"
            value={operator}
            onChange={(e) => setOperator(e.target.value as CustomRuleOperator)}
          >
            {OPERATOR_OPTIONS.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </Select>
        </div>

        <div className="space-y-1.5">
          <Label htmlFor="custom-rule-operator-argument" className="text-foreground">
            Operator argument
          </Label>
          <Input
            id="custom-rule-operator-argument"
            type="text"
            required
            value={operatorArgument}
            onChange={(e) => setOperatorArgument(e.target.value)}
            placeholder="(?i)curl"
          />
        </div>

        <div className="space-y-1.5">
          <Label htmlFor="custom-rule-actions" className="text-foreground">
            Actions
          </Label>
          <Input
            id="custom-rule-actions"
            type="text"
            required
            value={actions}
            onChange={(e) => setActions(e.target.value)}
            placeholder="deny,status:403,log"
          />
        </div>

        <div className="space-y-1.5">
          <Label htmlFor="custom-rule-comment" className="text-foreground">
            Comment
          </Label>
          <Input
            id="custom-rule-comment"
            type="text"
            value={comment}
            onChange={(e) => setComment(e.target.value)}
            placeholder="Optional"
          />
        </div>

        <div className="flex items-center gap-2">
          <Checkbox
            id="custom-rule-is-active"
            checked={isActive}
            onChange={(e) => setIsActive(e.target.checked)}
          />
          <Label htmlFor="custom-rule-is-active" className="text-foreground">
            Active
          </Label>
        </div>
      </form>
    </Modal>
  );
}

type DeleteCustomRuleDialogProps = {
  policyId: number;
  rule: CustomRule;
  onSuccess: () => void;
  onClose: () => void;
};

export function DeleteCustomRuleDialog({
  policyId,
  rule,
  onSuccess,
  onClose,
}: DeleteCustomRuleDialogProps) {
  const { accessToken } = useAuth();
  const [submitting, setSubmitting] = useState(false);
  const [serverError, setServerError] = useState<string | null>(null);

  async function handleDelete() {
    if (!accessToken) return;

    setSubmitting(true);
    setServerError(null);

    try {
      await deleteCustomRule(accessToken, policyId, rule.id);
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
      title="Delete custom rule"
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
        Are you sure you want to delete custom rule{" "}
        <span className="font-semibold text-fg">{rule.rule_id}</span>?
        This action cannot be undone.
      </p>
    </Modal>
  );
}
