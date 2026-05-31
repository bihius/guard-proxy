import { type FormEvent, useState } from "react";

import { Modal } from "@/components/shared/Modal";
import { useAuth } from "@/hooks/use-auth";
import { ApiError } from "@/lib/api-client";

import { createPolicy, updatePolicy } from "./api";
import type { Policy } from "./types";

type CreateMode = { mode: "create" };
type EditMode = { mode: "edit"; policy: Policy };

type PolicyFormModalProps = (CreateMode | EditMode) & {
  onSuccess: () => void;
  onClose: () => void;
};

export function PolicyFormModal(props: PolicyFormModalProps) {
  const { onSuccess, onClose } = props;
  const { accessToken } = useAuth();

  const initial = props.mode === "edit" ? props.policy : null;

  const [name, setName] = useState(initial?.name ?? "");
  const [description, setDescription] = useState(initial?.description ?? "");
  const [enforcementMode, setEnforcementMode] = useState<"block" | "detect_only">(
    initial?.enforcement_mode ?? "block",
  );
  const [paranoiaLevel, setParanoiaLevel] = useState<string>(
    String(initial?.paranoia_level ?? 1),
  );
  const [inboundThreshold, setInboundThreshold] = useState<string>(
    String(initial?.inbound_anomaly_threshold ?? 5),
  );
  const outboundThreshold = String(initial?.outbound_anomaly_threshold ?? 4);
  const [isActive, setIsActive] = useState(initial?.is_active ?? true);
  const [submitting, setSubmitting] = useState(false);
  const [serverError, setServerError] = useState<string | null>(null);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    if (!accessToken) return;

    setSubmitting(true);
    setServerError(null);

    try {
      if (props.mode === "edit") {
        await updatePolicy(accessToken, props.policy.id, {
          name,
          description: description || null,
          enforcement_mode: enforcementMode,
          paranoia_level: Number(paranoiaLevel) as 1 | 2 | 3 | 4,
          inbound_anomaly_threshold: Number(inboundThreshold),
          outbound_anomaly_threshold: Number(outboundThreshold),
          is_active: isActive,
        });
      } else {
        await createPolicy(accessToken, {
          name,
          description: description || null,
          enforcement_mode: enforcementMode,
          paranoia_level: Number(paranoiaLevel) as 1 | 2 | 3 | 4,
          inbound_anomaly_threshold: Number(inboundThreshold),
          outbound_anomaly_threshold: Number(outboundThreshold),
        });
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

  const title = props.mode === "create" ? "New policy" : "Edit policy";

  return (
    <Modal
      title={title}
      onClose={onClose}
      footer={
        <>
          <button type="button" onClick={onClose} className="btn-ghost px-4 py-2 text-sm">
            Cancel
          </button>
          <button
            type="submit"
            form="policy-form"
            disabled={submitting}
            className="btn-primary px-4 py-2 text-sm"
          >
            {submitting ? "Saving…" : props.mode === "create" ? "Create" : "Save"}
          </button>
        </>
      }
    >
      <form id="policy-form" onSubmit={(e) => void handleSubmit(e)} className="space-y-4">
        {serverError && (
          <div
            role="alert"
            aria-live="assertive"
            className="rounded-[var(--radius-md)] bg-error-soft px-4 py-3 text-sm font-medium text-error"
          >
            {serverError}
          </div>
        )}

        <div className="space-y-1.5">
          <label htmlFor="policy-name" className="block text-sm font-medium text-fg-muted">
            Name
          </label>
          <input
            id="policy-name"
            type="text"
            required
            maxLength={255}
            value={name}
            onChange={(e) => setName(e.target.value)}
            className="input-field"
            placeholder="My WAF policy"
          />
        </div>

        <div className="space-y-1.5">
          <label htmlFor="policy-description" className="block text-sm font-medium text-fg-muted">
            Description
          </label>
          <input
            id="policy-description"
            type="text"
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            className="input-field"
            placeholder="Optional"
          />
        </div>

        <div className="space-y-1.5">
          <label htmlFor="policy-enforcement-mode" className="block text-sm font-medium text-fg-muted">
            Enforcement mode
          </label>
          <select
            id="policy-enforcement-mode"
            value={enforcementMode}
            onChange={(e) => setEnforcementMode(e.target.value as "block" | "detect_only")}
            className="input-field"
          >
            <option value="block">Block</option>
            <option value="detect_only">Detect only</option>
          </select>
        </div>

        <div className="space-y-1.5">
          <label htmlFor="policy-paranoia-level" className="block text-sm font-medium text-fg-muted">
            Paranoia level
          </label>
          <select
            id="policy-paranoia-level"
            value={paranoiaLevel}
            onChange={(e) => setParanoiaLevel(e.target.value)}
            className="input-field"
          >
            <option value="1">1 — Minimal</option>
            <option value="2">2 — Low</option>
            <option value="3">3 — High</option>
            <option value="4">4 — Maximum</option>
          </select>
        </div>

        <div className="space-y-1.5">
          <label htmlFor="policy-inbound-threshold" className="block text-sm font-medium text-fg-muted">
            Inbound threshold
          </label>
          <input
            id="policy-inbound-threshold"
            type="number"
            required
            min={1}
            value={inboundThreshold}
            onChange={(e) => setInboundThreshold(e.target.value)}
            className="input-field"
          />
        </div>

        {props.mode === "edit" && (
          <label className="flex cursor-pointer items-center gap-2 text-sm font-medium text-fg-muted">
            <input
              type="checkbox"
              checked={isActive}
              onChange={(e) => setIsActive(e.target.checked)}
              className="h-4 w-4 accent-accent"
            />
            Active
          </label>
        )}
      </form>
    </Modal>
  );
}
