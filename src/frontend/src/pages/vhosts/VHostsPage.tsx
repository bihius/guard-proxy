import { useState } from "react";

import type { DataTableColumn } from "@/components/shared/DataTable";
import { DataTable } from "@/components/shared/DataTable";
import { ErrorState } from "@/components/shared/ErrorState";
import { LoadingState } from "@/components/shared/LoadingState";
import { PageHeader } from "@/components/shared/PageHeader";
import { SectionCard } from "@/components/shared/SectionCard";
import { StatusBadge } from "@/components/shared/StatusBadge";
import { DeleteVHostDialog } from "@/features/vhosts/DeleteVHostDialog";
import { VHostFormModal } from "@/features/vhosts/VHostFormModal";
import { useVHosts } from "@/features/vhosts/use-vhosts";
import type { VHost } from "@/features/vhosts/types";
import { useAuth } from "@/hooks/use-auth";

type ModalState =
  | null
  | { type: "create" }
  | { type: "edit"; vhost: VHost }
  | { type: "delete"; vhost: VHost };

export function VHostsPage() {
  const { hasRole } = useAuth();
  const { vhosts, policies, policyNameById, isLoading, error, refresh } = useVHosts();
  const [modal, setModal] = useState<ModalState>(null);
  const isAdmin = hasRole("admin");

  function closeAndRefresh() {
    setModal(null);
    refresh();
  }

  const columns: DataTableColumn<VHost>[] = [
    {
      key: "domain",
      header: "Domain",
      cell: (row) => (
        <div className="space-y-1">
          <p className="font-medium text-fg">{row.domain}</p>
          <p className="font-mono text-xs text-fg-subtle">{row.backend_url}</p>
        </div>
      ),
    },
    {
      key: "policy",
      header: "Policy",
      cell: (row) =>
        row.policy_id != null
          ? (policyNameById[row.policy_id] ?? `#${row.policy_id}`)
          : <span className="text-fg-subtle">None</span>,
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
            cell: (row: VHost) => (
              <div className="flex items-center gap-2">
                <button
                  type="button"
                  onClick={() => setModal({ type: "edit", vhost: row })}
                  className="btn-ghost rounded-[var(--radius-sm)] px-3 py-1.5 text-xs font-semibold"
                >
                  Edit
                </button>
                <button
                  type="button"
                  onClick={() => setModal({ type: "delete", vhost: row })}
                  className="rounded-[var(--radius-sm)] px-3 py-1.5 text-xs font-semibold text-error transition hover:bg-error-soft"
                >
                  Delete
                </button>
              </div>
            ),
          } satisfies DataTableColumn<VHost>,
        ]
      : []),
  ];

  return (
    <section className="space-y-8">
      <PageHeader
        eyebrow="VHosts"
        title="Virtual hosts"
        description="Manage the domains, backend targets, and WAF policies for each virtual host."
        actions={
          isAdmin ? (
            <button
              type="button"
              onClick={() => setModal({ type: "create" })}
              className="btn-primary px-4 py-2 text-sm"
            >
              New vhost
            </button>
          ) : undefined
        }
      />

      <SectionCard title="Registered hosts" description="All configured virtual hosts and their current status.">
        {isLoading ? (
          <LoadingState label="Loading virtual hosts…" />
        ) : error ? (
          <ErrorState
            title="Failed to load virtual hosts"
            description={error}
            action={
              <button
                type="button"
                onClick={refresh}
                className="btn-ghost px-4 py-2 text-sm"
              >
                Retry
              </button>
            }
          />
        ) : (
          <DataTable
            columns={columns}
            rows={vhosts}
            getRowKey={(row) => String(row.id)}
            emptyTitle="No virtual hosts yet"
            emptyDescription="Create your first virtual host to start routing traffic through Guard Proxy."
          />
        )}
      </SectionCard>

      {modal?.type === "create" && (
        <VHostFormModal
          mode="create"
          policies={policies}
          onSuccess={closeAndRefresh}
          onClose={() => setModal(null)}
        />
      )}

      {modal?.type === "edit" && (
        <VHostFormModal
          mode="edit"
          vhost={modal.vhost}
          policies={policies}
          onSuccess={closeAndRefresh}
          onClose={() => setModal(null)}
        />
      )}

      {modal?.type === "delete" && (
        <DeleteVHostDialog
          vhost={modal.vhost}
          onSuccess={closeAndRefresh}
          onClose={() => setModal(null)}
        />
      )}
    </section>
  );
}
