import type { DataTableColumn } from "@/components/shared/DataTable";

import { DataTable } from "@/components/shared/DataTable";
import { PageHeader } from "@/components/shared/PageHeader";
import { SectionCard } from "@/components/shared/SectionCard";
import { StatusBadge } from "@/components/shared/StatusBadge";

type VHostRow = {
  id: string;
  domain: string;
  policy: string;
  status: "Active" | "Inactive";
  backendUrl: string;
};

const vhostRows: VHostRow[] = [
  {
    id: "vh-1",
    domain: "app.example.com",
    policy: "Default",
    status: "Active",
    backendUrl: "https://backend-app.internal",
  },
  {
    id: "vh-2",
    domain: "admin.example.com",
    policy: "Strict",
    status: "Active",
    backendUrl: "https://backend-admin.internal",
  },
  {
    id: "vh-3",
    domain: "legacy.example.com",
    policy: "Permissive",
    status: "Inactive",
    backendUrl: "http://legacy.internal:8080",
  },
];

const columns: DataTableColumn<VHostRow>[] = [
  {
    key: "domain",
    header: "Domain",
    cell: (row) => (
      <div className="space-y-1">
        <p className="font-medium text-fg">{row.domain}</p>
        <p className="text-xs text-fg-subtle">{row.id}</p>
      </div>
    ),
  },
  {
    key: "policy",
    header: "Policy",
    cell: (row) => row.policy,
  },
  {
    key: "status",
    header: "Status",
    cell: (row) => (
      <StatusBadge
        label={row.status}
        tone={row.status === "Active" ? "success" : "warning"}
      />
    ),
  },
  {
    key: "backendUrl",
    header: "Backend URL",
    cell: (row) => (
      <span className="font-mono text-xs text-fg-muted">{row.backendUrl}</span>
    ),
  },
];

export function VHostsPage() {
  return (
    <section className="space-y-8">
      <PageHeader
        eyebrow="VHosts"
        title="Virtual hosts inventory"
        description="This starter screen shows the shared DataTable component in the shape the team will later reuse for real VHost data."
        actions={<StatusBadge label="Mock data" tone="info" />}
      />

      <SectionCard
        title="Registered hosts"
        description="Example table layout for domains, assigned policies, and backend targets."
      >
        <DataTable
          columns={columns}
          rows={vhostRows}
          getRowKey={(row) => row.id}
          emptyTitle="No virtual hosts yet"
          emptyDescription="Once the real API is connected, this table will become the main entry point for browsing configured domains."
        />
      </SectionCard>
    </section>
  );
}
