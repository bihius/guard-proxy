import { useState } from "react";
import { Link } from "react-router-dom";

import type { DataTableColumn } from "@/components/shared/DataTable";
import { DataTable } from "@/components/shared/DataTable";
import { ErrorState } from "@/components/shared/ErrorState";
import { LoadingState } from "@/components/shared/LoadingState";
import { PageHeader } from "@/components/shared/PageHeader";
import { SectionCard } from "@/components/shared/SectionCard";
import { StatusBadge } from "@/components/shared/StatusBadge";
import { Button } from "@/components/ui/button";
import { DeletePolicyDialog } from "@/features/policies/DeletePolicyDialog";
import { PolicyFormModal } from "@/features/policies/PolicyFormModal";
import type { Policy } from "@/features/policies/types";
import { usePolicies } from "@/features/policies/use-policies";
import { useAuth } from "@/hooks/use-auth";
import { getPolicyDetailPath } from "@/app/routes";

type ModalState =
  | null
  | { type: "create" }
  | { type: "edit"; policy: Policy }
  | { type: "delete"; policy: Policy };

export function PoliciesPage() {
  const { hasRole } = useAuth();
  const { policies, assignedPolicyIds, isLoading, error, refresh } = usePolicies();
  const [modal, setModal] = useState<ModalState>(null);
  const isAdmin = hasRole("admin");

  function closeAndRefresh() {
    setModal(null);
    refresh();
  }

  const columns: DataTableColumn<Policy>[] = [
    {
      key: "name",
      header: "Name",
      cell: (row) => (
        <Link
          to={getPolicyDetailPath(row.id)}
          className="font-medium text-foreground hover:underline"
        >
          {row.name}
        </Link>
      ),
    },
    {
      key: "enforcement_mode",
      header: "Enforcement mode",
      cell: (row) => (
        <StatusBadge
          label={row.enforcement_mode === "block" ? "Block" : "Detect only"}
          tone={row.enforcement_mode === "block" ? "info" : "warning"}
        />
      ),
    },
    {
      key: "paranoia_level",
      header: "Paranoia level",
      cell: (row) => String(row.paranoia_level),
    },
    {
      key: "thresholds",
      header: "Inbound threshold",
      cell: (row) => (
        <span className="tabular-nums text-foreground">
          {row.inbound_anomaly_threshold}
        </span>
      ),
    },
    {
      key: "status",
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
            cell: (row: Policy) => {
              const assigned = assignedPolicyIds.has(row.id);
              return (
                <div className="flex items-center gap-2">
                  <Button
                    type="button"
                    onClick={() => setModal({ type: "edit", policy: row })}
                    variant="outline"
                    size="sm"
                  >
                    Edit
                  </Button>
                  <span
                    title={
                      assigned
                        ? "Cannot delete because this policy is assigned to a virtual host"
                        : undefined
                    }
                  >
                    <Button
                      type="button"
                      disabled={assigned}
                      onClick={() => setModal({ type: "delete", policy: row })}
                      variant="destructive"
                      size="sm"
                    >
                      Delete
                    </Button>
                  </span>
                </div>
              );
            },
          } satisfies DataTableColumn<Policy>,
        ]
      : []),
  ];

  return (
    <section className="space-y-8">
      <PageHeader
        title="WAF policies"
        description="Manage CRS-based WAF policies and assign them to virtual hosts."
        actions={
          isAdmin ? (
            <Button
              type="button"
              onClick={() => setModal({ type: "create" })}
            >
              New policy
            </Button>
          ) : undefined
        }
      />

      <SectionCard title="Policies" description="All configured WAF policies and their current settings.">
        {isLoading ? (
          <LoadingState label="Loading policies…" />
        ) : error ? (
          <ErrorState
            title="Failed to load policies"
            description={error}
            action={
              <Button
                type="button"
                onClick={refresh}
                variant="outline"
              >
                Retry
              </Button>
            }
          />
        ) : (
          <DataTable
            columns={columns}
            rows={policies}
            getRowKey={(row) => String(row.id)}
            emptyTitle="No policies yet"
            emptyDescription="Create your first WAF policy to start protecting your virtual hosts."
          />
        )}
      </SectionCard>

      {modal?.type === "create" && (
        <PolicyFormModal
          mode="create"
          onSuccess={closeAndRefresh}
          onClose={() => setModal(null)}
        />
      )}

      {modal?.type === "edit" && (
        <PolicyFormModal
          mode="edit"
          policy={modal.policy}
          onSuccess={closeAndRefresh}
          onClose={() => setModal(null)}
        />
      )}

      {modal?.type === "delete" && (
        <DeletePolicyDialog
          policy={modal.policy}
          onSuccess={closeAndRefresh}
          onClose={() => setModal(null)}
        />
      )}
    </section>
  );
}
