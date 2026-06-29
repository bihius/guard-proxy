import { useCallback, useEffect, useRef, useState } from "react";
import { useParams } from "react-router-dom";

import type { DataTableColumn } from "@/components/shared/DataTable";
import { DataTable } from "@/components/shared/DataTable";
import { ErrorState } from "@/components/shared/ErrorState";
import { LoadingState } from "@/components/shared/LoadingState";
import { PageHeader } from "@/components/shared/PageHeader";
import { SectionCard } from "@/components/shared/SectionCard";
import { StatusBadge } from "@/components/shared/StatusBadge";
import { listRuleOverrides } from "@/features/policies/api";
import {
  DeleteRuleOverrideDialog,
  RuleOverrideFormModal,
  type RuleOverrideModalState,
} from "@/features/policies/RuleOverrideModals";
import type { RuleOverride } from "@/features/policies/types";
import { getVHost, listAllPolicies, updateVHost } from "@/features/vhosts/api";
import type { Policy, VHostDetail } from "@/features/vhosts/types";
import { useAuth } from "@/hooks/use-auth";
import { ApiError } from "@/lib/api-client";

function formatDate(value: string) {
  return new Intl.DateTimeFormat(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(new Date(value));
}

export function VHostDetailPage() {
  const { vhostId } = useParams();
  const { accessToken, hasRole } = useAuth();
  const [vhost, setVHost] = useState<VHostDetail | null>(null);
  const [policies, setPolicies] = useState<Policy[]>([]);
  const [ruleOverrides, setRuleOverrides] = useState<RuleOverride[]>([]);
  const [selectedPolicyId, setSelectedPolicyId] = useState("");
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [policyError, setPolicyError] = useState<string | null>(null);
  const [savingPolicy, setSavingPolicy] = useState(false);
  const [overrideModal, setOverrideModal] = useState<RuleOverrideModalState>(null);
  const refreshCountRef = useRef(0);
  const isAdmin = hasRole("admin");

  const load = useCallback(() => {
    if (!accessToken) return;

    const parsedVHostId = Number(vhostId);
    if (!Number.isInteger(parsedVHostId) || parsedVHostId <= 0) {
      setError("Invalid virtual host ID");
      setIsLoading(false);
      return;
    }

    const controller = new AbortController();
    const generation = ++refreshCountRef.current;

    setIsLoading(true);
    setError(null);
    setPolicyError(null);

    Promise.all([
      getVHost(accessToken, parsedVHostId, controller.signal),
      listAllPolicies(accessToken, controller.signal),
    ])
      .then(async ([vhostDetail, policyList]) => {
        let overrides: RuleOverride[] = [];

        if (vhostDetail.policy_id != null) {
          overrides = await listRuleOverrides(
            accessToken,
            vhostDetail.policy_id,
            controller.signal,
          );
        }

        if (generation !== refreshCountRef.current) return;
        setVHost(vhostDetail);
        setPolicies(policyList);
        setRuleOverrides(overrides);
        setSelectedPolicyId(
          vhostDetail.policy_id != null ? String(vhostDetail.policy_id) : "",
        );
        setIsLoading(false);
      })
      .catch((err: unknown) => {
        if (generation !== refreshCountRef.current) return;
        if (err instanceof Error && err.name === "AbortError") return;
        setError(err instanceof Error ? err.message : "Failed to load virtual host");
        setIsLoading(false);
      });

    return () => controller.abort();
  }, [accessToken, vhostId]);

  useEffect(() => {
    const cleanup = load();
    return cleanup;
  }, [load]);

  async function handlePolicySave() {
    if (!accessToken || !vhost) return;

    setSavingPolicy(true);
    setPolicyError(null);

    try {
      await updateVHost(accessToken, vhost.id, {
        policy_id: selectedPolicyId ? Number(selectedPolicyId) : null,
      });
      load();
    } catch (err) {
      setPolicyError(
        err instanceof ApiError ? err.detail : "An unexpected error occurred",
      );
    } finally {
      setSavingPolicy(false);
    }
  }

  function closeOverrideModalAndRefresh() {
    setOverrideModal(null);
    load();
  }

  const overrideColumns: DataTableColumn<RuleOverride>[] = [
    { key: "rule_id", header: "Rule ID", cell: (row) => String(row.rule_id) },
    {
      key: "action",
      header: "Action",
      cell: (row) => (
        <StatusBadge
          label={row.action === "enable" ? "Enabled" : "Disabled"}
          tone={row.action === "enable" ? "success" : "warning"}
        />
      ),
    },
    {
      key: "comment",
      header: "Comment",
      cell: (row) =>
        row.comment ? (
          <span>{row.comment}</span>
        ) : (
          <span className="text-fg-subtle">None</span>
        ),
    },
    {
      key: "created_at",
      header: "Created",
      cell: (row) => (
        <span className="text-fg-muted">{formatDate(row.created_at)}</span>
      ),
    },
    ...(isAdmin && vhost?.policy_id != null
      ? [
          {
            key: "actions",
            header: "",
            className: "w-px whitespace-nowrap",
            cell: (row: RuleOverride) => (
              <div className="flex items-center gap-2">
                <button
                  type="button"
                  onClick={() =>
                    setOverrideModal({
                      type: "edit",
                      policyId: vhost.policy_id as number,
                      override: row,
                    })
                  }
                  className="rounded-[var(--radius-sm)] border border-border bg-surface-hover px-3 py-1.5 text-xs font-semibold text-fg-muted transition hover:text-fg"
                >
                  Edit
                </button>
                <button
                  type="button"
                  onClick={() =>
                    setOverrideModal({
                      type: "delete",
                      policyId: vhost.policy_id as number,
                      override: row,
                    })
                  }
                  className="rounded-[var(--radius-sm)] border border-error/50 px-3 py-1.5 text-xs font-semibold text-error transition hover:border-error hover:bg-error-soft"
                >
                  Delete
                </button>
              </div>
            ),
          } satisfies DataTableColumn<RuleOverride>,
        ]
      : []),
  ];

  const selectedPolicyChanged =
    selectedPolicyId !== (vhost?.policy_id != null ? String(vhost.policy_id) : "");
  const assignedPolicyName =
    vhost?.policy?.name ??
    policies.find((policy) => String(policy.id) === selectedPolicyId)?.name ??
    null;

  return (
    <section className="space-y-8">
      <PageHeader
        title={vhost ? vhost.domain : "Virtual host detail"}
        description={vhost?.description ?? undefined}
      />

      {isLoading ? (
        <LoadingState label="Loading virtual host..." />
      ) : error ? (
        <ErrorState
          title="Failed to load virtual host"
          description={error}
          action={
            <button
              type="button"
              onClick={load}
              className="btn-ghost px-4 py-2 text-sm"
            >
              Retry
            </button>
          }
        />
      ) : vhost ? (
        <>
          <SectionCard
            title="Virtual host"
            description="Domain, backend target, and routing status."
          >
            <dl className="grid grid-cols-1 gap-x-8 gap-y-4 text-sm sm:grid-cols-2 lg:grid-cols-3">
              <div>
                <dt className="font-medium text-fg-muted">Domain</dt>
                <dd className="mt-1 font-medium text-fg">{vhost.domain}</dd>
              </div>
              <div>
                <dt className="font-medium text-fg-muted">Backends</dt>
                <dd className="mt-1 space-y-2">
                  {vhost.backends.map((backend) => (
                    <div key={backend.id} className="space-y-1">
                      <p className="break-all font-mono text-xs text-fg">
                        {backend.url}
                      </p>
                      <p className="text-xs text-fg-muted">
                        {backend.is_active ? "Active" : "Inactive"} -{" "}
                        {backend.health_check_enabled
                          ? `check ${backend.health_check_path} every ${backend.health_check_interval_seconds}s`
                          : "health checks disabled"}
                      </p>
                    </div>
                  ))}
                </dd>
              </div>
              <div>
                <dt className="font-medium text-fg-muted">Status</dt>
                <dd className="mt-1">
                  <StatusBadge
                    label={vhost.is_active ? "Active" : "Inactive"}
                    tone={vhost.is_active ? "success" : "warning"}
                  />
                </dd>
              </div>
              <div>
                <dt className="font-medium text-fg-muted">SSL</dt>
                <dd className="mt-1">
                  <StatusBadge
                    label={vhost.ssl_enabled ? "Enabled" : "Disabled"}
                    tone={vhost.ssl_enabled ? "success" : "warning"}
                  />
                </dd>
              </div>
              <div>
                <dt className="font-medium text-fg-muted">SSL Provider</dt>
                <dd className="mt-1 font-medium text-fg">
                  {vhost.ssl_provider === "letsencrypt" ? "Let's Encrypt" : vhost.ssl_provider === "upload" ? "Custom Certificate" : "None"}
                </dd>
              </div>
              <div>
                <dt className="font-medium text-fg-muted">SSL Expires</dt>
                <dd className="mt-1 font-medium text-fg">
                  {vhost.ssl_expires_at ? formatDate(vhost.ssl_expires_at) : "N/A"}
                </dd>
              </div>
              <div>
                <dt className="font-medium text-fg-muted">Created</dt>
                <dd className="mt-1 text-fg">{formatDate(vhost.created_at)}</dd>
              </div>
              <div>
                <dt className="font-medium text-fg-muted">Updated</dt>
                <dd className="mt-1 text-fg">{formatDate(vhost.updated_at)}</dd>
              </div>
            </dl>
          </SectionCard>

          <SectionCard
            title="Assigned policy"
            description="WAF policy currently attached to this virtual host."
          >
            {policyError && (
              <div
                role="alert"
                aria-live="assertive"
                className="mb-4 rounded-[var(--radius-md)] bg-error-soft px-4 py-3 text-sm font-medium text-error"
              >
                {policyError}
              </div>
            )}

            {isAdmin ? (
              <div className="flex flex-col gap-3 sm:flex-row sm:items-end">
                <div className="min-w-0 flex-1 space-y-1.5">
                  <label htmlFor="vhost-policy-assignment" className="block text-sm font-medium text-fg-muted">
                    Policy
                  </label>
                  <select
                    id="vhost-policy-assignment"
                    value={selectedPolicyId}
                    onChange={(e) => setSelectedPolicyId(e.target.value)}
                    className="input-field"
                  >
                    <option value="">None</option>
                    {policies.map((policy) => (
                      <option key={policy.id} value={String(policy.id)}>
                        {policy.name}
                      </option>
                    ))}
                  </select>
                </div>
                <button
                  type="button"
                  disabled={!selectedPolicyChanged || savingPolicy}
                  onClick={() => void handlePolicySave()}
                  className="btn-primary px-4 py-2 text-sm disabled:opacity-50"
                >
                  {savingPolicy ? "Saving..." : "Save policy"}
                </button>
              </div>
            ) : (
              <p className="text-sm text-fg">
                {assignedPolicyName ?? (
                  <span className="text-fg-subtle">No policy assigned</span>
                )}
              </p>
            )}

            {vhost.policy ? (
              <dl className="mt-5 grid grid-cols-2 gap-x-8 gap-y-4 text-sm sm:grid-cols-4">
                <div>
                  <dt className="font-medium text-fg-muted">Enforcement</dt>
                  <dd className="mt-1">
                    <StatusBadge
                      label={
                        vhost.policy.enforcement_mode === "block"
                          ? "Block"
                          : "Detect only"
                      }
                      tone={
                        vhost.policy.enforcement_mode === "block"
                          ? "info"
                          : "warning"
                      }
                    />
                  </dd>
                </div>
                <div>
                  <dt className="font-medium text-fg-muted">Policy status</dt>
                  <dd className="mt-1">
                    <StatusBadge
                      label={vhost.policy.is_active ? "Active" : "Inactive"}
                      tone={vhost.policy.is_active ? "success" : "warning"}
                    />
                  </dd>
                </div>
                <div>
                  <dt className="font-medium text-fg-muted">Paranoia level</dt>
                  <dd className="mt-1 text-fg">{vhost.policy.paranoia_level}</dd>
                </div>
                <div>
                  <dt className="font-medium text-fg-muted">Inbound threshold</dt>
                  <dd className="mt-1 text-fg">
                    {vhost.policy.inbound_anomaly_threshold}
                  </dd>
                </div>
              </dl>
            ) : (
              <p className="mt-5 text-sm text-fg-muted">No policy assigned</p>
            )}
          </SectionCard>

          <SectionCard
            title="Rule overrides"
            description="Individual CRS rules enabled or disabled for the assigned policy."
            actions={
              isAdmin && vhost.policy_id != null ? (
                <button
                  type="button"
                  onClick={() =>
                    setOverrideModal({
                      type: "create",
                      policyId: vhost.policy_id as number,
                    })
                  }
                  className="btn-primary px-4 py-2 text-sm"
                >
                  Add override
                </button>
              ) : undefined
            }
          >
            {vhost.policy_id == null ? (
              <div className="rounded-[var(--radius-lg)] border border-border bg-surface px-4 py-6 text-sm text-fg-muted">
                No policy assigned
              </div>
            ) : (
              <DataTable
                columns={overrideColumns}
                rows={ruleOverrides}
                getRowKey={(row) => String(row.id)}
                emptyTitle="No rule overrides"
                emptyDescription="All CRS rules follow the assigned policy settings."
              />
            )}
          </SectionCard>

          {overrideModal?.type === "create" && (
            <RuleOverrideFormModal
              mode="create"
              policyId={overrideModal.policyId}
              onSuccess={closeOverrideModalAndRefresh}
              onClose={() => setOverrideModal(null)}
            />
          )}

          {overrideModal?.type === "edit" && (
            <RuleOverrideFormModal
              mode="edit"
              policyId={overrideModal.policyId}
              override={overrideModal.override}
              onSuccess={closeOverrideModalAndRefresh}
              onClose={() => setOverrideModal(null)}
            />
          )}

          {overrideModal?.type === "delete" && (
            <DeleteRuleOverrideDialog
              policyId={overrideModal.policyId}
              override={overrideModal.override}
              onSuccess={closeOverrideModalAndRefresh}
              onClose={() => setOverrideModal(null)}
            />
          )}
        </>
      ) : null}
    </section>
  );
}
