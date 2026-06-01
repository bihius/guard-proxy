import { Modal } from "@/components/shared/Modal";
import { StatusBadge } from "@/components/shared/StatusBadge";

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

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="grid grid-cols-[10rem_1fr] gap-2 py-1.5">
      <dt className="text-sm font-medium text-fg-muted">{label}</dt>
      <dd className="text-sm text-fg">{children}</dd>
    </div>
  );
}

function Nullable({ value }: { value: string | number | null | undefined }) {
  return value !== null && value !== undefined ? <>{value}</> : <span className="text-fg-subtle">—</span>;
}

export function LogDetailModal({ log, onClose }: LogDetailModalProps) {
  return (
    <Modal
      title="Event details"
      onClose={onClose}
      footer={
        <button type="button" onClick={onClose} className="btn-ghost px-4 py-2 text-sm">
          Close
        </button>
      }
    >
      <div className="max-h-[60vh] overflow-y-auto">
        <dl className="divide-y divide-border-subtle">
          <Field label="Timestamp">{new Date(log.event_at).toLocaleString()}</Field>
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
          <Field label="Message">
            <Nullable value={log.message} />
          </Field>
          <Field label="VHost ID">
            <Nullable value={log.vhost_id} />
          </Field>
          <Field label="Policy ID">
            <Nullable value={log.policy_id} />
          </Field>
          <Field label="Producer event ID">
            <Nullable value={log.producer_event_id} />
          </Field>
          {log.raw_context !== null && (
            <Field label="Raw context">
              <pre className="overflow-auto rounded-[var(--radius-md)] bg-surface-hover p-2 text-xs">
                {JSON.stringify(log.raw_context, null, 2)}
              </pre>
            </Field>
          )}
        </dl>
      </div>
    </Modal>
  );
}
