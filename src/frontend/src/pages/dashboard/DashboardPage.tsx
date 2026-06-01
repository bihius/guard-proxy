import { useState, type ReactNode } from "react";

import {
  AlertTriangleIcon,
  PulseIcon,
  ServerIcon,
  ShieldIcon,
} from "@/components/icons";
import { PageHeader } from "@/components/shared/PageHeader";
import { RoleBadge } from "@/components/shared/RoleBadge";
import { SectionCard } from "@/components/shared/SectionCard";
import { StatCard } from "@/components/shared/StatCard";
import { StatusBadge } from "@/components/shared/StatusBadge";
import { ApplyConfigButton } from "@/features/runtime/ApplyConfigButton";
import type { ApplyResult } from "@/features/runtime/ApplyConfigButton";
import { RuntimeStatusCard } from "@/features/runtime/RuntimeStatusCard";
import { useRuntimeStatus } from "@/features/runtime/use-runtime-status";
import { useDashboardStats } from "@/features/dashboard/use-dashboard-stats";
import { useAuth } from "@/hooks/use-auth";

export function DashboardPage() {
  const { role } = useAuth();
  const runtimeStatus = useRuntimeStatus();
  const stats = useDashboardStats();
  const [applyResult, setApplyResult] = useState<ApplyResult | null>(null);

  return (
    <section className="space-y-8">
      <PageHeader
        title="Security operations overview"
        description="This starter dashboard shows the shared building blocks for the rest of the team: stat cards, section cards, and consistent status badges."
        actions={
          <>
            {role ? <RoleBadge role={role} /> : null}
            <StatusBadge label="Development" tone="info" />
            <ApplyConfigButton
              runtimeStatus={runtimeStatus}
              onResult={(result) => setApplyResult(result)}
            />
          </>
        }
      />

      {applyResult ? (
        <div
          className={`flex items-start justify-between gap-4 rounded-[var(--radius-md)] border px-4 py-3 text-sm font-medium ${
            applyResult.kind === "success"
              ? "border-success/30 bg-success-soft text-success"
              : "border-error/30 bg-error-soft text-error"
          }`}
        >
          <span>{applyResult.message}</span>
          <button
            type="button"
            onClick={() => setApplyResult(null)}
            className="shrink-0 text-current opacity-60 hover:opacity-100"
          >
            ✕
          </button>
        </div>
      ) : null}

      <div className="grid gap-5 md:grid-cols-2 xl:grid-cols-4">
        <StatCard
          label="Protected vhosts"
          value={
            stats.vhosts.error || stats.vhosts.count === null
              ? "—"
              : String(stats.vhosts.count)
          }
          hint="Number of virtual hosts currently configured in the WAF."
          tone="info"
          icon={<ServerIcon />}
          isLoading={stats.vhosts.isLoading}
        />
        <StatCard
          label="Active policies"
          value={
            stats.policies.error || stats.policies.count === null
              ? "—"
              : String(stats.policies.count)
          }
          hint="Policies define the WAF behaviour applied to host traffic."
          tone="success"
          icon={<ShieldIcon />}
          isLoading={stats.policies.isLoading}
        />
        <StatCard
          label="Blocked requests"
          value={
            stats.blocked.error || stats.blocked.count === null
              ? "—"
              : String(stats.blocked.count)
          }
          hint="Total requests denied by Coraza rules (action: deny)."
          tone="warning"
          icon={<AlertTriangleIcon />}
          isLoading={stats.blocked.isLoading}
        />
        <StatCard
          label="Critical alerts"
          value={
            stats.alerts.error || stats.alerts.count === null
              ? "—"
              : String(stats.alerts.count)
          }
          hint="Log entries with severity: critical across all hosts."
          tone="error"
          icon={<PulseIcon />}
          isLoading={stats.alerts.isLoading}
        />
      </div>

      <div className="grid gap-5 xl:grid-cols-[1.25fr_1fr]">
        <SectionCard
          title="Recent activity"
          description="Example of a section-level card that a teammate can later fill with API data."
        >
          <div className="space-y-4">
            <ActivityRow
              title="Admin signed in"
              description="Authentication wiring is now connected to the frontend shell."
              badge={<StatusBadge label="Healthy" tone="success" />}
            />
            <ActivityRow
              title="Route protection enabled"
              description="Unauthorized users are redirected away from protected pages."
              badge={<StatusBadge label="Active" tone="info" />}
            />
            <ActivityRow
              title="Shared UI kit ready"
              description="New screens can reuse shared cards, badges, and state blocks."
              badge={<StatusBadge label="Bootstrap" tone="warning" />}
            />
          </div>
        </SectionCard>

        <RuntimeStatusCard status={runtimeStatus} />
      </div>
    </section>
  );
}

type ActivityRowProps = {
  title: string;
  description: string;
  badge: ReactNode;
};

function ActivityRow({ title, description, badge }: ActivityRowProps) {
  return (
    <div className="flex flex-col gap-3 rounded-[var(--radius-md)] border border-border bg-surface p-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h3 className="text-sm font-semibold text-fg">{title}</h3>
        {badge}
      </div>
      <p className="text-sm leading-6 text-fg-muted">{description}</p>
    </div>
  );
}
