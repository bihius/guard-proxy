import { useState } from "react";
import { useNavigate } from "react-router-dom";

import { getVHostDetailPath } from "@/app/routes";
import type { DataTableColumn } from "@/components/shared/DataTable";
import { DataTable } from "@/components/shared/DataTable";
import { ErrorState } from "@/components/shared/ErrorState";
import { LoadingState } from "@/components/shared/LoadingState";
import { PageHeader } from "@/components/shared/PageHeader";
import { SectionCard } from "@/components/shared/SectionCard";
import { StatusBadge } from "@/components/shared/StatusBadge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
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
  const navigate = useNavigate();
  const { hasRole } = useAuth();
  const {
    vhosts,
    total,
    page,
    pageSize,
    searchQuery,
    policies,
    policyNameById,
    isLoading,
    error,
    setPage,
    setSearchQuery,
    refresh,
  } = useVHosts();
  const [modal, setModal] = useState<ModalState>(null);
  const isAdmin = hasRole("admin");
  const totalPages = Math.max(1, Math.ceil(total / pageSize));

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
          <p className="font-medium text-foreground">{row.domain}</p>
          <p className="font-mono text-xs text-muted-foreground">{row.backend_url}</p>
        </div>
      ),
    },
    {
      key: "policy",
      header: "Policy",
      cell: (row) =>
        row.policy_id != null
          ? (policyNameById[row.policy_id] ?? `#${row.policy_id}`)
          : <span className="text-muted-foreground">None</span>,
    },
    {
      key: "ssl",
      header: "SSL",
      cell: (row) => (
        <div className="space-y-1">
          <StatusBadge
            label={row.ssl_enabled ? "Enabled" : "Disabled"}
            tone={row.ssl_enabled ? "success" : "warning"}
          />
          {row.ssl_enabled && (
            <p className="text-xs text-muted-foreground mt-1">
              {row.ssl_provider === "letsencrypt" ? "Let's Encrypt" : row.ssl_provider === "upload" ? "Custom" : "None"}
            </p>
          )}
        </div>
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
            cell: (row: VHost) => (
              // Keep Edit/Delete clicks from triggering row navigation.
              <div
                className="flex items-center gap-2"
                onClick={(event) => event.stopPropagation()}
              >
                <Button
                  type="button"
                  onClick={() => setModal({ type: "edit", vhost: row })}
                  variant="outline"
                  size="sm"
                >
                  Edit
                </Button>
                <Button
                  type="button"
                  onClick={() => setModal({ type: "delete", vhost: row })}
                  variant="destructive"
                  size="sm"
                >
                  Delete
                </Button>
              </div>
            ),
          } satisfies DataTableColumn<VHost>,
        ]
      : []),
  ];

  return (
    <section className="space-y-8">
      <PageHeader
        title="Virtual hosts"
        description="Manage the domains, backend targets, and WAF policies for each virtual host."
        actions={
          isAdmin ? (
            <Button
              type="button"
              onClick={() => setModal({ type: "create" })}
            >
              New vhost
            </Button>
          ) : undefined
        }
      />

      <SectionCard
        title="Registered hosts"
        description="All configured virtual hosts and their current status."
        actions={
          <Input
            aria-label="Search virtual hosts"
            className="w-full sm:w-72"
            placeholder="Search domains"
            value={searchQuery}
            onChange={(event) => setSearchQuery(event.target.value)}
          />
        }
      >
        {isLoading ? (
          <LoadingState label="Loading virtual hosts…" />
        ) : error ? (
          <ErrorState
            title="Failed to load virtual hosts"
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
          <>
            <DataTable
              columns={columns}
              rows={vhosts}
              getRowKey={(row) => String(row.id)}
              onRowClick={(row) => navigate(getVHostDetailPath(row.id))}
              emptyTitle="No virtual hosts found"
              emptyDescription="Create a virtual host or adjust the search query."
            />

            {total > 0 && (
              <div className="mt-4 flex items-center justify-between gap-4">
                <span className="text-sm text-muted-foreground">
                  Page {page} of {totalPages} · {total} virtual hosts
                </span>
                <div className="flex gap-2">
                  <Button
                    type="button"
                    onClick={() => setPage(page - 1)}
                    disabled={page <= 1}
                    variant="outline"
                  >
                    Prev
                  </Button>
                  <Button
                    type="button"
                    onClick={() => setPage(page + 1)}
                    disabled={page >= totalPages}
                    variant="outline"
                  >
                    Next
                  </Button>
                </div>
              </div>
            )}
          </>
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
