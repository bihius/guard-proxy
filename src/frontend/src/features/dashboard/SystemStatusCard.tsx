import { ErrorState } from "@/components/shared/ErrorState";
import { SectionCard } from "@/components/shared/SectionCard";
import { StatusBadge } from "@/components/shared/StatusBadge";
import { Alert } from "@/components/ui/alert";
import type { RuntimeStatusState } from "@/features/runtime/RuntimeStatusCard";
import type { DeploymentState } from "@/features/runtime/types";

import { formatRelativeTime } from "./format";
import type { OverviewResponse } from "./types";

type SystemStatusCardProps = {
  status: RuntimeStatusState;
  overview: OverviewResponse | null;
};

const deploymentToneMap: Record<DeploymentState, "success" | "error" | "warning"> = {
  deployed: "success",
  failed: "error",
  never_deployed: "warning",
};

const deploymentLabelMap: Record<DeploymentState, string> = {
  deployed: "Deployed",
  failed: "Failed",
  never_deployed: "Never deployed",
};

function truncateChecksum(checksum: string | null): string {
  return checksum ? checksum.slice(0, 12) : "—";
}

function StatusRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-center justify-between gap-3 py-2.5">
      <span className="text-sm text-muted-foreground">{label}</span>
      <span className="tabular-figures font-mono text-sm text-foreground">{value}</span>
    </div>
  );
}

/**
 * Deployment health plus the inventory the WAF is protecting.
 *
 * Replaces the dashboard's old runtime card: same checksums, but it also
 * answers "is what I edited actually live?" by comparing the generated config
 * against the one HAProxy last reloaded.
 */
export function SystemStatusCard({ status, overview }: SystemStatusCardProps) {
  if (status.error || (!status.isLoading && !status.data)) {
    return (
      <SectionCard title="System status">
        <ErrorState
          title="Could not load status"
          description={status.error ?? "Unknown error"}
        />
      </SectionCard>
    );
  }

  if (status.isLoading && !status.data) {
    return (
      <SectionCard title="System status">
        <div className="space-y-3" role="status" aria-label="Loading system status">
          {[0, 1, 2, 3].map((row) => (
            <div key={row} className="h-6 animate-pulse rounded-md bg-muted" />
          ))}
        </div>
      </SectionCard>
    );
  }

  const data = status.data!;
  const { deployment_state, generated_config, latest_reload } = data;
  const hasPendingChanges =
    generated_config.checksum !== null &&
    generated_config.checksum !== latest_reload?.config_checksum;

  return (
    <SectionCard
      title="System status"
      actions={
        <StatusBadge
          label={deploymentLabelMap[deployment_state]}
          tone={deploymentToneMap[deployment_state]}
        />
      }
    >
      <div className="space-y-4">
        {hasPendingChanges ? (
          <Alert variant="warning">
            Configuration changes have not been applied yet — the running proxy is
            still on an older config.
          </Alert>
        ) : null}

        {latest_reload?.status === "failed" && latest_reload.message ? (
          <Alert variant="destructive">{latest_reload.message}</Alert>
        ) : null}

        <div className="divide-y divide-border-subtle">
          <StatusRow
            label="Protected vhosts"
            value={
              overview
                ? `${overview.protected_vhosts} / ${overview.total_vhosts}`
                : "—"
            }
          />
          <StatusRow
            label="Active policies"
            value={overview ? String(overview.active_policies) : "—"}
          />
          <StatusRow
            label="Generated config"
            value={truncateChecksum(generated_config.checksum)}
          />
          <StatusRow
            label="Running config"
            value={truncateChecksum(latest_reload?.config_checksum ?? null)}
          />
          <StatusRow
            label="Last reload"
            value={
              latest_reload ? formatRelativeTime(latest_reload.created_at) : "never"
            }
          />
        </div>
      </div>
    </SectionCard>
  );
}
