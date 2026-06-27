import { useCallback, useEffect, useRef, useState } from "react";
import { useParams } from "react-router-dom";

import type { DataTableColumn } from "@/components/shared/DataTable";
import { DataTable } from "@/components/shared/DataTable";
import { ErrorState } from "@/components/shared/ErrorState";
import { LoadingState } from "@/components/shared/LoadingState";
import { PageHeader } from "@/components/shared/PageHeader";
import { SectionCard } from "@/components/shared/SectionCard";
import { StatusBadge } from "@/components/shared/StatusBadge";
import { Button } from "@/components/ui/button";
import { getPolicy } from "@/features/policies/api";
import {
  CustomRuleFormModal,
  DeleteCustomRuleDialog,
  type CustomRuleModalState,
} from "@/features/policies/CustomRuleModals";
import {
  DeleteRuleExclusionDialog,
  RuleExclusionFormModal,
  type RuleExclusionModalState,
} from "@/features/policies/RuleExclusionModals";
import {
  DeleteRuleOverrideDialog,
  RuleOverrideFormModal,
  type RuleOverrideModalState,
} from "@/features/policies/RuleOverrideModals";
import type {
  CustomRule,
  PolicyDetail,
  RuleExclusion,
  RuleOverride,
} from "@/features/policies/types";
import { useAuth } from "@/hooks/use-auth";

export function PolicyDetailPage() {
  const { policyId } = useParams();
  const { accessToken, hasRole } = useAuth();
  const [policy, setPolicy] = useState<PolicyDetail | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [overrideModal, setOverrideModal] = useState<RuleOverrideModalState>(null);
  const [exclusionModal, setExclusionModal] = useState<RuleExclusionModalState>(null);
  const [customRuleModal, setCustomRuleModal] = useState<CustomRuleModalState>(null);
  const refreshCountRef = useRef(0);
  const isAdmin = hasRole("admin");

  const load = useCallback(() => {
    if (!accessToken || !policyId) return;

    const controller = new AbortController();
    const generation = ++refreshCountRef.current;

    setIsLoading(true);
    setError(null);

    getPolicy(accessToken, Number(policyId), controller.signal)
      .then((data) => {
        if (generation !== refreshCountRef.current) return;
        setPolicy(data);
        setIsLoading(false);
      })
      .catch((err: unknown) => {
        if (generation !== refreshCountRef.current) return;
        if (err instanceof Error && err.name === "AbortError") return;
        setError(err instanceof Error ? err.message : "Failed to load policy");
        setIsLoading(false);
      });

    return () => controller.abort();
  }, [accessToken, policyId]);

  useEffect(() => {
    const cleanup = load();
    return cleanup;
  }, [load]);

  function closeOverrideModalAndRefresh() {
    setOverrideModal(null);
    load();
  }

  function closeExclusionModalAndRefresh() {
    setExclusionModal(null);
    load();
  }

  function closeCustomRuleModalAndRefresh() {
    setCustomRuleModal(null);
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
          <span className="text-muted-foreground">—</span>
        ),
    },
    ...(isAdmin
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
                      policyId: policy!.id,
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
                      policyId: policy!.id,
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

  const exclusionColumns: DataTableColumn<RuleExclusion>[] = [
    { key: "rule_id", header: "Rule ID", cell: (row) => String(row.rule_id) },
    { key: "target_type", header: "Target type", cell: (row) => row.target_type },
    { key: "target_value", header: "Target value", cell: (row) => row.target_value },
    {
      key: "scope_path",
      header: "Scope path",
      cell: (row) =>
        row.scope_path ? (
          <span>{row.scope_path}</span>
        ) : (
          <span className="text-muted-foreground">All paths</span>
        ),
    },
    {
      key: "comment",
      header: "Comment",
      cell: (row) =>
        row.comment ? (
          <span>{row.comment}</span>
        ) : (
          <span className="text-muted-foreground">—</span>
        ),
    },
    ...(isAdmin
      ? [
          {
            key: "actions",
            header: "",
            className: "w-px whitespace-nowrap",
            cell: (row: RuleExclusion) => (
              <div className="flex items-center gap-2">
                <button
                  type="button"
                  onClick={() =>
                    setExclusionModal({
                      type: "edit",
                      policyId: policy!.id,
                      exclusion: row,
                    })
                  }
                  className="rounded-[var(--radius-sm)] border border-border bg-surface-hover px-3 py-1.5 text-xs font-semibold text-fg-muted transition hover:text-fg"
                >
                  Edit
                </button>
                <button
                  type="button"
                  onClick={() =>
                    setExclusionModal({
                      type: "delete",
                      policyId: policy!.id,
                      exclusion: row,
                    })
                  }
                  className="rounded-[var(--radius-sm)] border border-error/50 px-3 py-1.5 text-xs font-semibold text-error transition hover:border-error hover:bg-error-soft"
                >
                  Delete
                </button>
              </div>
            ),
          } satisfies DataTableColumn<RuleExclusion>,
        ]
      : []),
  ];

  const customRuleColumns: DataTableColumn<CustomRule>[] = [
    { key: "rule_id", header: "Rule ID", cell: (row) => String(row.rule_id) },
    { key: "phase", header: "Phase", cell: (row) => row.phase },
    { key: "variables", header: "Variables", cell: (row) => row.variables },
    { key: "operator", header: "Operator", cell: (row) => row.operator },
    {
      key: "is_active",
      header: "Status",
      cell: (row) => (
        <StatusBadge
          label={row.is_active ? "Active" : "Inactive"}
          tone={row.is_active ? "success" : "warning"}
        />
      ),
    },
    ...(isAdmin
      ? [
          {
            key: "actions",
            header: "",
            className: "w-px whitespace-nowrap",
            cell: (row: CustomRule) => (
              <div className="flex items-center gap-2">
                <button
                  type="button"
                  onClick={() =>
                    setCustomRuleModal({
                      type: "edit",
                      policyId: policy!.id,
                      rule: row,
                    })
                  }
                  className="rounded-[var(--radius-sm)] border border-border bg-surface-hover px-3 py-1.5 text-xs font-semibold text-fg-muted transition hover:text-fg"
                >
                  Edit
                </button>
                <button
                  type="button"
                  onClick={() =>
                    setCustomRuleModal({
                      type: "delete",
                      policyId: policy!.id,
                      rule: row,
                    })
                  }
                  className="rounded-[var(--radius-sm)] border border-error/50 px-3 py-1.5 text-xs font-semibold text-error transition hover:border-error hover:bg-error-soft"
                >
                  Delete
                </button>
              </div>
            ),
          } satisfies DataTableColumn<CustomRule>,
        ]
      : []),
  ];

  return (
    <section className="space-y-8">
      <PageHeader
        title={policy ? policy.name : "Policy detail"}
        description={policy?.description ?? undefined}
      />

      {isLoading ? (
        <LoadingState label="Loading policy…" />
      ) : error ? (
        <ErrorState
          title="Failed to load policy"
          description={error}
          action={
            <Button
              type="button"
              onClick={load}
              variant="outline"
            >
              Retry
            </Button>
          }
        />
      ) : policy ? (
        <>
          <SectionCard
            title="Policy settings"
            description="Current configuration for this WAF policy."
            descriptionDisplay="tooltip"
          >
            <dl className="grid gap-4 text-sm sm:grid-cols-2 xl:grid-cols-4">
              <div>
                <dt className="font-medium text-muted-foreground">Enforcement mode</dt>
                <dd className="mt-1">
                  <StatusBadge
                    label={policy.enforcement_mode === "block" ? "Block" : "Detect only"}
                    tone={policy.enforcement_mode === "block" ? "info" : "warning"}
                  />
                </dd>
              </div>
              <div>
                <dt className="font-medium text-muted-foreground">Status</dt>
                <dd className="mt-1">
                  <StatusBadge
                    label={policy.is_active ? "Active" : "Inactive"}
                    tone={policy.is_active ? "success" : "warning"}
                  />
                </dd>
              </div>
              <div>
                <dt className="font-medium text-muted-foreground">Paranoia level</dt>
                <dd className="mt-1 text-foreground">{policy.paranoia_level}</dd>
              </div>
              <div>
                <dt className="font-medium text-muted-foreground">Inbound threshold</dt>
                <dd className="mt-1 text-foreground">{policy.inbound_anomaly_threshold}</dd>
              </div>
            </dl>
          </SectionCard>

          <SectionCard
            title="Rule overrides"
            description="Individual CRS rules enabled or disabled for this policy."
            descriptionDisplay="tooltip"
            actions={
              isAdmin ? (
                <button
                  type="button"
                  onClick={() => setOverrideModal({ type: "create", policyId: policy.id })}
                  className="btn-primary px-4 py-2 text-sm"
                >
                  Add override
                </button>
              ) : undefined
            }
          >
            <DataTable
              columns={overrideColumns}
              rows={policy.rule_overrides}
              getRowKey={(row) => String(row.id)}
              emptyTitle="No rule overrides"
              emptyDescription="All CRS rules follow the default paranoia level settings."
            />
          </SectionCard>

          <SectionCard
            title="Rule exclusions"
            description="Targets narrowed out of CRS rule inspection for this policy."
            descriptionDisplay="tooltip"
            actions={
              isAdmin ? (
                <button
                  type="button"
                  onClick={() => setExclusionModal({ type: "create", policyId: policy.id })}
                  className="btn-primary px-4 py-2 text-sm"
                >
                  Add exclusion
                </button>
              ) : undefined
            }
          >
            <DataTable
              columns={exclusionColumns}
              rows={policy.rule_exclusions}
              getRowKey={(row) => String(row.id)}
              emptyTitle="No rule exclusions"
              emptyDescription="No CRS rule targets are currently excluded for this policy."
            />
          </SectionCard>

          <SectionCard
            title="Custom rules"
            description="Administrator-authored rules in the reserved 9000000–9099999 range."
            descriptionDisplay="tooltip"
            actions={
              isAdmin ? (
                <button
                  type="button"
                  onClick={() => setCustomRuleModal({ type: "create", policyId: policy.id })}
                  className="btn-primary px-4 py-2 text-sm"
                >
                  Add custom rule
                </button>
              ) : undefined
            }
          >
            <DataTable
              columns={customRuleColumns}
              rows={policy.custom_rules}
              getRowKey={(row) => String(row.id)}
              emptyTitle="No custom rules"
              emptyDescription="No custom rules have been defined for this policy."
            />
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

          {exclusionModal?.type === "create" && (
            <RuleExclusionFormModal
              mode="create"
              policyId={exclusionModal.policyId}
              onSuccess={closeExclusionModalAndRefresh}
              onClose={() => setExclusionModal(null)}
            />
          )}
          {exclusionModal?.type === "edit" && (
            <RuleExclusionFormModal
              mode="edit"
              policyId={exclusionModal.policyId}
              exclusion={exclusionModal.exclusion}
              onSuccess={closeExclusionModalAndRefresh}
              onClose={() => setExclusionModal(null)}
            />
          )}
          {exclusionModal?.type === "delete" && (
            <DeleteRuleExclusionDialog
              policyId={exclusionModal.policyId}
              exclusion={exclusionModal.exclusion}
              onSuccess={closeExclusionModalAndRefresh}
              onClose={() => setExclusionModal(null)}
            />
          )}

          {customRuleModal?.type === "create" && (
            <CustomRuleFormModal
              mode="create"
              policyId={customRuleModal.policyId}
              onSuccess={closeCustomRuleModalAndRefresh}
              onClose={() => setCustomRuleModal(null)}
            />
          )}
          {customRuleModal?.type === "edit" && (
            <CustomRuleFormModal
              mode="edit"
              policyId={customRuleModal.policyId}
              rule={customRuleModal.rule}
              onSuccess={closeCustomRuleModalAndRefresh}
              onClose={() => setCustomRuleModal(null)}
            />
          )}
          {customRuleModal?.type === "delete" && (
            <DeleteCustomRuleDialog
              policyId={customRuleModal.policyId}
              rule={customRuleModal.rule}
              onSuccess={closeCustomRuleModalAndRefresh}
              onClose={() => setCustomRuleModal(null)}
            />
          )}
        </>
      ) : null}
    </section>
  );
}
