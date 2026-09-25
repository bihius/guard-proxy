import { useState, type ReactNode } from "react";
import { Link } from "react-router-dom";

import { getPolicyDetailPath } from "@/app/routes";
import { Modal } from "@/components/shared/Modal";
import { StatusBadge } from "@/components/shared/StatusBadge";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { RuleExclusionFormModal } from "@/features/policies/RuleExclusionModals";
import type { RuleExclusionSuggestion } from "@/features/policies/types";
import { useConfigChanged } from "@/features/runtime/use-config-changed";
import { useAuth } from "@/hooks/use-auth";
import { ApiError } from "@/lib/api-client";
import { formatDateTime } from "@/lib/datetime";

import { suggestExclusion } from "./api";
import type { Log, LogAction, LogSeverity } from "./types";

type LogDetailModalProps = {
  log: Log;
  onClose: () => void;
};

function actionTone(action: LogAction) {
  if (action === "deny") return "error" as const;
  if (action === "monitor") return "warning" as const;
  return "success" as const;
}

function severityTone(severity: LogSeverity) {
  if (severity === "critical" || severity === "error") return "error" as const;
  if (severity === "warning") return "warning" as const;
  return "info" as const;
}

function Field({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="grid gap-1 py-2 sm:grid-cols-[10rem_1fr] sm:gap-2">
      <dt className="text-sm font-medium text-muted-foreground">{label}</dt>
      <dd className="text-sm text-foreground">{children}</dd>
    </div>
  );
}

function Nullable({ value }: { value: string | number | null | undefined }) {
  return value !== null && value !== undefined ? <>{value}</> : <span className="text-muted-foreground">—</span>;
}

function SuggestionIntro({ suggestion }: { suggestion: RuleExclusionSuggestion }) {
  if (suggestion.target_type !== null) {
    return (
      <p className="text-sm text-muted-foreground">
        Pre-filled from this event. Rule {suggestion.rule_id} matched{" "}
        <span className="font-mono text-foreground">{suggestion.matched_variable}</span>. Review
        the values before saving.
      </p>
    );
  }
  return (
    <Alert>
      {suggestion.matched_variable
        ? `Rule ${suggestion.rule_id} matched ${suggestion.matched_variable}, which Guard Proxy cannot exclude yet. `
        : `The variable rule ${suggestion.rule_id} matched could not be read from this event. `}
      Choose the target type and value yourself.
    </Alert>
  );
}

export function LogDetailModal({ log, onClose }: LogDetailModalProps) {
  const { accessToken, hasRole } = useAuth();
  const { notifyConfigChanged } = useConfigChanged();
  const [showRawContext, setShowRawContext] = useState(false);
  const [suggestion, setSuggestion] = useState<RuleExclusionSuggestion | null>(null);
  const [isSuggesting, setIsSuggesting] = useState(false);
  const [suggestError, setSuggestError] = useState<string | null>(null);
  const [createdInPolicy, setCreatedInPolicy] = useState<number | null>(null);

  // Exclusions belong to a policy and target one rule, so events without
  // either cannot produce one; creating them is admin-only.
  const canCreateExclusion = hasRole("admin") && log.rule_id !== null && log.policy_id !== null;

  async function startExclusion() {
    if (!accessToken) return;
    setIsSuggesting(true);
    setSuggestError(null);
    try {
      setSuggestion(await suggestExclusion(accessToken, log.id));
    } catch (err) {
      setSuggestError(err instanceof ApiError ? err.detail : "Could not prepare the exclusion");
    } finally {
      setIsSuggesting(false);
    }
  }

  // Swap the dialogs instead of stacking them: one modal at a time keeps
  // focus handling and Escape predictable.
  if (suggestion !== null) {
    return (
      <RuleExclusionFormModal
        mode="create"
        policyId={suggestion.policy_id}
        suggestion={suggestion}
        intro={<SuggestionIntro suggestion={suggestion} />}
        onSuccess={() => {
          notifyConfigChanged();
          setCreatedInPolicy(suggestion.policy_id);
          setSuggestion(null);
        }}
        onClose={() => setSuggestion(null)}
      />
    );
  }

  return (
    <Modal
      title="Event details"
      onClose={onClose}
      contentClassName="max-w-[min(80vw,72rem)]"
      footer={
        <>
          {canCreateExclusion && createdInPolicy === null && (
            <Button type="button" onClick={() => void startExclusion()} disabled={isSuggesting}>
              {isSuggesting ? "Preparing..." : "Create exclusion"}
            </Button>
          )}
          <Button type="button" onClick={onClose} variant="outline">
            Close
          </Button>
        </>
      }
    >
      {suggestError && (
        <Alert variant="destructive" aria-live="assertive" className="mb-3">
          {suggestError}
        </Alert>
      )}
      {createdInPolicy !== null && (
        <Alert aria-live="polite" className="mb-3">
          Exclusion saved to{" "}
          <Link to={getPolicyDetailPath(createdInPolicy)} className="font-medium underline">
            {log.policy_name ?? "the policy"}
          </Link>
          . It takes effect after you apply the configuration.
        </Alert>
      )}
      <div className="max-h-[60vh] overflow-y-auto">
        <dl className="divide-y divide-border-subtle">
          <Field label="Timestamp">{formatDateTime(log.event_at)}</Field>
          <Field label="VHost">{log.vhost}</Field>
          <Field label="Action">
            <StatusBadge label={log.action} tone={actionTone(log.action)} />
          </Field>
          <Field label="Severity">
            <StatusBadge label={log.severity} tone={severityTone(log.severity)} />
          </Field>
          <Field label="Method">
            <span className="font-mono text-xs">{log.method}</span>
          </Field>
          <Field label="Request URI">
            <span className="break-all font-mono text-xs">{log.request_uri}</span>
          </Field>
          <Field label="Source IP">{log.source_ip}</Field>
          <Field label="Status code">
            <Nullable value={log.status_code} />
          </Field>
          <Field label="Anomaly score">
            <Nullable value={log.anomaly_score} />
          </Field>
          <Field label="Paranoia level">
            <Nullable value={log.paranoia_level} />
          </Field>
          <Field label="Rule ID">
            <Nullable value={log.rule_id} />
          </Field>
          <Field label="Rule message">
            <Nullable value={log.rule_message} />
          </Field>
          <Field label="Policy">
            <Nullable value={log.policy_name} />
          </Field>
          <Field label="Producer event ID">
            <Nullable value={log.producer_event_id} />
          </Field>
          {log.raw_context !== null && (
            <Field label="Raw context">
              <div className="space-y-2">
                <Button
                  type="button"
                  onClick={() => setShowRawContext((current) => !current)}
                  variant="outline"
                  size="sm"
                  aria-expanded={showRawContext}
                >
                  {showRawContext ? "Hide raw context" : "Show raw context"}
                </Button>
                {showRawContext && (
                  <pre className="max-h-80 max-w-full overflow-y-auto overflow-x-hidden whitespace-pre-wrap break-words rounded-md bg-muted p-3 text-xs text-foreground">
                    {JSON.stringify(log.raw_context, null, 2)}
                  </pre>
                )}
              </div>
            </Field>
          )}
        </dl>
      </div>
    </Modal>
  );
}
