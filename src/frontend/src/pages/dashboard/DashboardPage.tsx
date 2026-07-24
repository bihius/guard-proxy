import type { ReactNode } from "react";

import {
  AlertTriangleIcon,
  BanIcon,
  PulseIcon,
  ServerIcon,
  ShieldIcon,
} from "@/components/icons";
import { PageHeader } from "@/components/shared/PageHeader";
import { RoleBadge } from "@/components/shared/RoleBadge";
import { SectionCard } from "@/components/shared/SectionCard";
import { StatCard } from "@/components/shared/StatCard";
import { StatusBadge } from "@/components/shared/StatusBadge";
import { RuntimeStatusCard } from "@/features/runtime/RuntimeStatusCard";
import { useRuntimeStatus } from "@/features/runtime/use-runtime-status";
import { useDashboardStats } from "@/features/dashboard/use-dashboard-stats";
import { useAuth } from "@/hooks/use-auth";

export function DashboardPage() {
  const { role, hasRole } = useAuth();
  const isAdmin = hasRole("admin");
  const runtimeStatus = useRuntimeStatus();
  const stats = useDashboardStats();

  return (
    <section className="space-y-8">
      <PageHeader
        title="Security operations overview"
        description="This starter dashboard shows the shared building blocks for the rest of the team: stat cards, section cards, and consistent status badges."
        actions={
          <>
            {role ? <RoleBadge role={role} /> : null}
            <StatusBadge label="Development" tone="info" />
          </>
        }
      />

      <div
        className={
          isAdmin
            ? "grid gap-5 md:grid-cols-2 xl:grid-cols-5"
            : "grid gap-5 md:grid-cols-2 xl:grid-cols-4"
        }
      >
        <StatCard
          label="Protected vhosts"
          value={
            stats.vhosts.error || stats.vhosts.count === null
              ? "—"
              : String(stats.vhosts.count)
          }
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
          tone="error"
          icon={<PulseIcon />}
          isLoading={stats.alerts.isLoading}
        />
        {isAdmin && (
          <StatCard
            label="Banned IPs"
            value={
              stats.bannedIps.error || stats.bannedIps.count === null
                ? "—"
                : String(stats.bannedIps.count)
            }
            tone="error"
            icon={<BanIcon />}
            isLoading={stats.bannedIps.isLoading}
          />
        )}
      </div>

      <div className="grid gap-5 xl:grid-cols-[1.25fr_1fr]">
        <SectionCard
          title="Recent activity"
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
    <div className="flex flex-col gap-3 rounded-lg border border-border bg-card p-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h3 className="text-sm font-semibold text-foreground">{title}</h3>
        {badge}
      </div>
      <p className="text-sm leading-6 text-muted-foreground">{description}</p>
    </div>
  );
}
