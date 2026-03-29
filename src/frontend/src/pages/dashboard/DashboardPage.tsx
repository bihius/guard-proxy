import type { ReactNode } from "react";

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

export function DashboardPage() {
  return (
    <section className="space-y-8">
      <PageHeader
        eyebrow="Dashboard"
        title="Security operations overview"
        description="This starter dashboard shows the shared building blocks for the rest of the team: stat cards, section cards, and consistent status badges."
        actions={
          <>
            <RoleBadge role="admin" />
            <StatusBadge label="Development" tone="info" />
          </>
        }
      />

      <div className="grid gap-5 md:grid-cols-2 xl:grid-cols-4">
        <StatCard
          label="Protected vhosts"
          value="12"
          hint="Soon this card will be fed by the real VHosts endpoint."
          tone="info"
          icon={<ServerIcon />}
        />
        <StatCard
          label="Active policies"
          value="4"
          hint="Policies define the WAF behavior applied to host traffic."
          tone="success"
          icon={<ShieldIcon />}
        />
        <StatCard
          label="Blocked requests"
          value="128"
          hint="This is placeholder data for the future monitoring view."
          tone="warning"
          icon={<AlertTriangleIcon />}
        />
        <StatCard
          label="Critical alerts"
          value="0"
          hint="Good example of a stat card that can stay calm until needed."
          tone="error"
          icon={<PulseIcon />}
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

        <SectionCard
          title="Quick status"
          description="Small composable status block for future platform health indicators."
        >
          <div className="space-y-3">
            <StatusRow
              label="Frontend shell"
              badge={<StatusBadge label="Ready" tone="success" />}
            />
            <StatusRow
              label="Auth foundation"
              badge={<StatusBadge label="Ready" tone="success" />}
            />
            <StatusRow
              label="Dashboard data"
              badge={<StatusBadge label="Mocked" tone="warning" />}
            />
          </div>
        </SectionCard>
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

type StatusRowProps = {
  label: string;
  badge: ReactNode;
};

function StatusRow({ label, badge }: StatusRowProps) {
  return (
    <div className="flex items-center justify-between gap-3 rounded-[var(--radius-md)] border border-border bg-surface p-4">
      <span className="text-sm font-medium text-fg">{label}</span>
      {badge}
    </div>
  );
}
