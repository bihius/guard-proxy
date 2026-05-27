import { ErrorState } from "@/components/shared/ErrorState";
import { LoadingState } from "@/components/shared/LoadingState";
import { SectionCard } from "@/components/shared/SectionCard";
import { StatusBadge } from "@/components/shared/StatusBadge";

import type { DeploymentState, RuntimeStatusResponse } from "./types";

export type RuntimeStatusState = {
  data: RuntimeStatusResponse | null;
  isLoading: boolean;
  error: string | null;
  refresh: () => void;
};

type RuntimeStatusCardProps = {
  status: RuntimeStatusState;
};

const deploymentToneMap: Record<
  DeploymentState,
  "success" | "error" | "warning"
> = {
  deployed: "success",
  failed: "error",
  never_deployed: "warning",
};

const deploymentLabelMap: Record<DeploymentState, string> = {
  deployed: "Deployed",
  failed: "Failed",
  never_deployed: "Never deployed",
};

function formatTimestamp(iso: string) {
  return new Date(iso).toLocaleString();
}

function truncateChecksum(checksum: string | null) {
  if (!checksum) return "—";
  return checksum.slice(0, 12);
}

export function RuntimeStatusCard({ status }: RuntimeStatusCardProps) {
  if (status.isLoading) {
    return (
      <SectionCard title="Runtime status" description="Current WAF deployment state.">
        <LoadingState label="Loading runtime status…" />
      </SectionCard>
    );
  }

  if (status.error || !status.data) {
    return (
      <SectionCard title="Runtime status" description="Current WAF deployment state.">
        <ErrorState
          title="Could not load status"
          description={status.error ?? "Unknown error"}
        />
      </SectionCard>
    );
  }

  const { deployment_state, generated_config, latest_reload } = status.data;
  const tone = deploymentToneMap[deployment_state];
  const label = deploymentLabelMap[deployment_state];

  return (
    <SectionCard
      title="Runtime status"
      description="Current WAF deployment state."
      actions={<StatusBadge label={label} tone={tone} />}
    >
      <div className="space-y-3">
        <StatusRow
          label="Generated checksum"
          value={truncateChecksum(generated_config.checksum)}
        />
        {latest_reload ? (
          <>
            <StatusRow
              label="Last reload checksum"
              value={truncateChecksum(latest_reload.config_checksum)}
            />
            <StatusRow
              label="Last reload"
              value={formatTimestamp(latest_reload.created_at)}
            />
            {latest_reload.status === "failed" && latest_reload.message ? (
              <div className="rounded-[var(--radius-md)] border border-error/30 bg-error-soft px-4 py-3 text-sm text-error">
                {latest_reload.message}
              </div>
            ) : null}
          </>
        ) : (
          <StatusRow label="Last reload" value="—" />
        )}
      </div>
    </SectionCard>
  );
}

function StatusRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-center justify-between gap-3 rounded-[var(--radius-md)] border border-border bg-surface p-4">
      <span className="text-sm font-medium text-fg">{label}</span>
      <span className="font-mono text-sm text-fg-muted">{value}</span>
    </div>
  );
}
