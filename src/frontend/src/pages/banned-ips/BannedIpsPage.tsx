import { useState } from "react";

import type { DataTableColumn } from "@/components/shared/DataTable";
import { DataTable } from "@/components/shared/DataTable";
import { ErrorState } from "@/components/shared/ErrorState";
import { LoadingState } from "@/components/shared/LoadingState";
import { PageHeader } from "@/components/shared/PageHeader";
import { SectionCard } from "@/components/shared/SectionCard";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { UnbanIpDialog } from "@/features/banned-ips/UnbanIpDialog";
import { useBannedIps } from "@/features/banned-ips/use-banned-ips";
import type { BannedIp } from "@/features/banned-ips/types";
import { useAuth } from "@/hooks/use-auth";

function formatExpiresIn(seconds: number) {
  if (seconds <= 0) return "Expiring";
  if (seconds < 60) return `${seconds}s`;
  const minutes = Math.ceil(seconds / 60);
  if (minutes < 60) return `${minutes}m`;
  const hours = Math.ceil(minutes / 60);
  return `${hours}h`;
}

export function BannedIpsPage() {
  const { hasRole } = useAuth();
  const {
    items,
    total,
    page,
    pageSize,
    searchQuery,
    isLoading,
    error,
    setPage,
    setSearchQuery,
    refresh,
  } = useBannedIps();
  const [unbanTarget, setUnbanTarget] = useState<BannedIp | null>(null);
  const isAdmin = hasRole("admin");
  const totalPages = Math.max(1, Math.ceil(total / pageSize));

  function closeAndRefresh() {
    setUnbanTarget(null);
    refresh();
  }

  const columns: DataTableColumn<BannedIp>[] = [
    {
      key: "ip",
      header: "IP address",
      cell: (row) => <span className="font-mono text-sm">{row.ip}</span>,
    },
    {
      key: "domain",
      header: "Domain",
      cell: (row) => row.domain,
    },
    {
      key: "violations",
      header: "Violations",
      cell: (row) => `${row.gpc0} / ${row.ban_threshold}`,
    },
    {
      key: "expires",
      header: "Expires in",
      cell: (row) => formatExpiresIn(row.expires_in_seconds),
    },
    ...(isAdmin
      ? [
          {
            key: "actions",
            header: "",
            className: "w-px whitespace-nowrap",
            cell: (row: BannedIp) => (
              <div
                className="flex items-center gap-2"
                onClick={(event) => event.stopPropagation()}
              >
                <Button
                  type="button"
                  onClick={() => setUnbanTarget(row)}
                  variant="destructive"
                  size="sm"
                >
                  Unban
                </Button>
              </div>
            ),
          } satisfies DataTableColumn<BannedIp>,
        ]
      : []),
  ];

  return (
    <section className="space-y-8">
      <PageHeader
        title="Banned IPs"
        description="Source IPs currently blocked by the auto-ban policies, tracked via the HAProxy Runtime API."
      />

      <SectionCard
        title="Banned addresses"
        description="Currently banned source IPs across all virtual hosts."
        actions={
          <Input
            aria-label="Search banned IPs"
            className="w-full sm:w-72"
            placeholder="Search IP address"
            value={searchQuery}
            onChange={(event) => setSearchQuery(event.target.value)}
          />
        }
      >
        {isLoading ? (
          <LoadingState label="Loading banned IPs…" />
        ) : error ? (
          <ErrorState
            title="Failed to load banned IPs"
            description={error}
            action={
              <Button type="button" onClick={refresh} variant="outline">
                Retry
              </Button>
            }
          />
        ) : (
          <>
            <DataTable
              columns={columns}
              rows={items}
              getRowKey={(row) => row.ip}
              emptyTitle="No banned IPs"
              emptyDescription="No source IPs are currently banned."
            />

            {total > 0 && (
              <div className="mt-4 flex items-center justify-between gap-4">
                <span className="text-sm text-muted-foreground">
                  Page {page} of {totalPages} · {total} banned IPs
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

      {unbanTarget && (
        <UnbanIpDialog
          bannedIp={unbanTarget}
          onSuccess={closeAndRefresh}
          onClose={() => setUnbanTarget(null)}
        />
      )}
    </section>
  );
}
