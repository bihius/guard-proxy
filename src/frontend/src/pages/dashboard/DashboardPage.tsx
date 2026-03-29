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
          icon={<AlertIcon />}
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
            <StatusRow label="Frontend shell" badge={<StatusBadge label="Ready" tone="success" />} />
            <StatusRow label="Auth foundation" badge={<StatusBadge label="Ready" tone="success" />} />
            <StatusRow label="Dashboard data" badge={<StatusBadge label="Mocked" tone="warning" />} />
          </div>
        </SectionCard>
      </div>
    </section>
  );
}

type ActivityRowProps = {
  title: string;
  description: string;
  badge: React.ReactNode;
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
  badge: React.ReactNode;
};

function StatusRow({ label, badge }: StatusRowProps) {
  return (
    <div className="flex items-center justify-between gap-3 rounded-[var(--radius-md)] border border-border bg-surface p-4">
      <span className="text-sm font-medium text-fg">{label}</span>
      {badge}
    </div>
  );
}

function ServerIcon() {
  return (
    <svg
      width="18"
      height="18"
      viewBox="0 0 18 18"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.5"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <rect x="3" y="3" width="12" height="4" rx="1.5" />
      <rect x="3" y="11" width="12" height="4" rx="1.5" />
      <line x1="6" y1="5" x2="6.01" y2="5" />
      <line x1="6" y1="13" x2="6.01" y2="13" />
    </svg>
  );
}

function ShieldIcon() {
  return (
    <svg
      width="18"
      height="18"
      viewBox="0 0 18 18"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.5"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <path d="M9 2.5 3.5 5v4.2c0 3.1 2 5.8 5.5 6.8 3.5-1 5.5-3.7 5.5-6.8V5L9 2.5Z" />
      <path d="m6.7 9.1 1.5 1.5 3-3.2" />
    </svg>
  );
}

function AlertIcon() {
  return (
    <svg
      width="18"
      height="18"
      viewBox="0 0 18 18"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.5"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <path d="M9 3.2 15 14H3L9 3.2Z" />
      <line x1="9" y1="7" x2="9" y2="10.5" />
      <circle cx="9" cy="12.8" r="0.5" fill="currentColor" />
    </svg>
  );
}

function PulseIcon() {
  return (
    <svg
      width="18"
      height="18"
      viewBox="0 0 18 18"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.5"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <polyline points="2.5 9.5 5.5 9.5 7.2 5.5 10.3 12.5 12.1 8.2 15.5 8.2" />
    </svg>
  );
}
