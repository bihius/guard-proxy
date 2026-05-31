import { type FormEvent, useState } from "react";

import { Modal } from "@/components/shared/Modal";
import { useAuth } from "@/hooks/use-auth";
import { ApiError } from "@/lib/api-client";

import { createVHost, updateVHost } from "./api";
import type { Policy, VHost } from "./types";

type CreateMode = { mode: "create" };
type EditMode = { mode: "edit"; vhost: VHost };

type VHostFormModalProps = (CreateMode | EditMode) & {
  policies: Policy[];
  onSuccess: () => void;
  onClose: () => void;
};

export function VHostFormModal(props: VHostFormModalProps) {
  const { policies, onSuccess, onClose } = props;
  const { accessToken } = useAuth();

  const initial = props.mode === "edit" ? props.vhost : null;

  const [domain, setDomain] = useState(initial?.domain ?? "");
  const [backendUrl, setBackendUrl] = useState(initial?.backend_url ?? "");
  const [description, setDescription] = useState(initial?.description ?? "");
  const [isActive, setIsActive] = useState(initial?.is_active ?? true);
  const [policyId, setPolicyId] = useState<string>(
    initial?.policy_id != null
      ? String(initial.policy_id)
      : String(policies[0]?.id ?? ""),
  );
  const [submitting, setSubmitting] = useState(false);
  const [serverError, setServerError] = useState<string | null>(null);

  const noPolicies = props.mode === "create" && policies.length === 0;

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    if (!accessToken) return;

    setSubmitting(true);
    setServerError(null);

    const body = {
      domain,
      backend_url: backendUrl,
      description: description || null,
      ssl_enabled: initial?.ssl_enabled ?? false,
      is_active: isActive,
      policy_id: Number(policyId),
    };

    try {
      if (props.mode === "edit") {
        await updateVHost(accessToken, props.vhost.id, body);
      } else {
        await createVHost(accessToken, body);
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

  const title = props.mode === "create" ? "New virtual host" : "Edit virtual host";

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
            form="vhost-form"
            disabled={submitting || noPolicies}
            className="btn-primary px-4 py-2 text-sm"
          >
            {submitting ? "Saving…" : props.mode === "create" ? "Create" : "Save"}
          </button>
        </>
      }
    >
      <form id="vhost-form" onSubmit={(e) => void handleSubmit(e)} className="space-y-4">
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
          <label htmlFor="vhost-domain" className="block text-sm font-medium text-fg-muted">
            Domain
          </label>
          <input
            id="vhost-domain"
            type="text"
            required
            maxLength={255}
            value={domain}
            onChange={(e) => setDomain(e.target.value)}
            className="input-field"
            placeholder="example.com"
          />
        </div>

        <div className="space-y-1.5">
          <label htmlFor="vhost-backend-url" className="block text-sm font-medium text-fg-muted">
            Backend URL
          </label>
          <input
            id="vhost-backend-url"
            type="url"
            required
            maxLength={512}
            value={backendUrl}
            onChange={(e) => setBackendUrl(e.target.value)}
            className="input-field"
            placeholder="https://backend.internal"
          />
        </div>

        <div className="space-y-1.5">
          <label htmlFor="vhost-description" className="block text-sm font-medium text-fg-muted">
            Description
          </label>
          <input
            id="vhost-description"
            type="text"
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            className="input-field"
            placeholder="Optional"
          />
        </div>

        <div className="space-y-1.5">
          <label htmlFor="vhost-policy" className="block text-sm font-medium text-fg-muted">
            Policy
          </label>
          <select
            id="vhost-policy"
            required
            value={policyId}
            onChange={(e) => setPolicyId(e.target.value)}
            className="input-field"
            disabled={noPolicies}
          >
            {policies.map((p) => (
              <option key={p.id} value={String(p.id)}>
                {p.name}
              </option>
            ))}
          </select>
          {noPolicies && (
            <p className="text-xs text-fg-muted">
              No policies yet — create one on the Policies page first.
            </p>
          )}
        </div>

        <label className="flex cursor-pointer items-center gap-2 text-sm font-medium text-fg-muted">
          <input
            type="checkbox"
            checked={isActive}
            onChange={(e) => setIsActive(e.target.checked)}
            className="h-4 w-4 accent-accent"
          />
          Active
        </label>
      </form>
    </Modal>
  );
}
