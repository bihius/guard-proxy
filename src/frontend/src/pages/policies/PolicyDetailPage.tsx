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
import type { PolicyDetail, RuleOverride } from "@/features/policies/types";
import { useAuth } from "@/hooks/use-auth";

export function PolicyDetailPage() {
  const { policyId } = useParams();
  const { accessToken } = useAuth();
  const [policy, setPolicy] = useState<PolicyDetail | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const refreshCountRef = useRef(0);

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
          >
            <DataTable
              columns={overrideColumns}
              rows={policy.rule_overrides}
              getRowKey={(row) => String(row.id)}
              emptyTitle="No rule overrides"
              emptyDescription="All CRS rules follow the default paranoia level settings."
            />
          </SectionCard>
        </>
      ) : null}
    </section>
  );
}
