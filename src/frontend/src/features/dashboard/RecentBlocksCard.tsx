import { ArrowRight } from "lucide-react";
import { Link, useNavigate } from "react-router-dom";

import { EmptyState } from "@/components/shared/EmptyState";
import { ErrorState } from "@/components/shared/ErrorState";
import { SectionCard } from "@/components/shared/SectionCard";
import { StatusBadge } from "@/components/shared/StatusBadge";
import { appRoutes } from "@/app/routes";
import type { Log, LogSeverity } from "@/features/logs/types";

import type { Resource } from "./use-dashboard-data";

type RecentBlocksCardProps = {
  blocks: Resource<Log[]>;
};

const severityTone: Record<LogSeverity, "error" | "warning" | "info" | "neutral"> = {
  critical: "error",
  error: "error",
  warning: "warning",
  info: "info",
};

function formatTime(iso: string): string {
  return new Date(iso).toLocaleTimeString(undefined, {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });
}

/** Live feed of the most recent denied requests, each a jump-off into the logs. */
export function RecentBlocksCard({ blocks }: RecentBlocksCardProps) {
  const navigate = useNavigate();

  const viewAll = (
    <Link
      to={`${appRoutes.logs}?action=deny`}
      className="flex items-center gap-1 text-sm font-medium text-primary transition-opacity duration-150 hover:opacity-80"
    >
      All logs
      <ArrowRight aria-hidden="true" className="h-4 w-4" />
    </Link>
  );

  if (blocks.error) {
    return (
      <SectionCard title="Recent blocks" actions={viewAll}>
        <ErrorState title="Could not load recent blocks" description={blocks.error} />
      </SectionCard>
    );
  }

  if (blocks.isLoading && blocks.data === null) {
    return (
      <SectionCard title="Recent blocks" actions={viewAll}>
        <div className="space-y-2" role="status" aria-label="Loading recent blocks">
          {[0, 1, 2, 3, 4].map((row) => (
            <div key={row} className="h-11 animate-pulse rounded-md bg-muted" />
          ))}
        </div>
      </SectionCard>
    );
  }

  const items = blocks.data ?? [];

  if (items.length === 0) {
    return (
      <SectionCard title="Recent blocks" actions={viewAll}>
        <EmptyState
          title="Nothing blocked yet"
          description="No request has been denied so far. Blocked traffic will show up here as soon as a rule fires."
        />
      </SectionCard>
    );
  }

  return (
    <SectionCard title="Recent blocks" actions={viewAll}>
      <ul className="divide-y divide-border-subtle">
        {items.map((log) => (
          <li key={log.id}>
            <button
              type="button"
              onClick={() =>
                navigate(
                  `${appRoutes.logs}?action=deny&source_ip=${encodeURIComponent(log.source_ip)}`,
                )
              }
              className="flex w-full cursor-pointer items-center gap-3 py-2.5 text-left transition-colors duration-150 hover:bg-surface-hover/60"
            >
              <span className="tabular-figures shrink-0 font-mono text-xs text-muted-foreground">
                {formatTime(log.event_at)}
              </span>
              <span className="shrink-0 font-mono text-xs text-foreground">
                {log.source_ip}
              </span>
              <span
                className="min-w-0 flex-1 truncate font-mono text-xs text-muted-foreground"
                title={`${log.method} ${log.request_uri}`}
              >
                {log.method} {log.request_uri}
              </span>
              <StatusBadge
                label={log.severity}
                tone={severityTone[log.severity] ?? "neutral"}
              />
            </button>
          </li>
        ))}
      </ul>
    </SectionCard>
  );
}
