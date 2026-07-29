import { ArrowRight, RefreshCw } from "lucide-react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";

import { appRoutes } from "@/app/routes";
import { AlertTriangleIcon, BanIcon, PulseIcon, ServerIcon } from "@/components/icons";
import { EmptyState } from "@/components/shared/EmptyState";
import { ErrorState } from "@/components/shared/ErrorState";
import { PageHeader } from "@/components/shared/PageHeader";
import { SectionCard } from "@/components/shared/SectionCard";
import { StatusBadge } from "@/components/shared/StatusBadge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { ActivityChart, ActivityChartLegend } from "@/features/dashboard/ActivityChart";
import { MetricTile } from "@/features/dashboard/MetricTile";
import { RecentBlocksCard } from "@/features/dashboard/RecentBlocksCard";
import { SystemStatusCard } from "@/features/dashboard/SystemStatusCard";
import { TimeRangeTabs } from "@/features/dashboard/TimeRangeTabs";
import { TopList } from "@/features/dashboard/TopList";
import type { TopListItem } from "@/features/dashboard/TopList";
import { formatCount } from "@/features/dashboard/format";
import { useDashboardData } from "@/features/dashboard/use-dashboard-data";
import {
  STATS_WINDOW_LABELS,
  isStatsWindow,
  type StatsWindow,
} from "@/features/dashboard/types";
import { useRuntimeStatus } from "@/features/runtime/use-runtime-status";
import { useAuth } from "@/hooks/use-auth";

const DEFAULT_WINDOW: StatsWindow = "24h";

export function DashboardPage() {
  const { hasRole } = useAuth();
  const isAdmin = hasRole("admin");
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();

  // The window lives in the URL so a view can be linked to and shared —
  // "look at what happened over the last hour" is a message people send.
  const rawWindow = searchParams.get("window");
  const window: StatsWindow = isStatsWindow(rawWindow) ? rawWindow : DEFAULT_WINDOW;

  const setWindow = (next: StatsWindow) => {
    const params = new URLSearchParams(searchParams);
    params.set("window", next);
    setSearchParams(params, { replace: true });
  };

  const runtimeStatus = useRuntimeStatus();
  const { overview, timeseries, top, recentBlocks, lastUpdatedAt, refresh } =
    useDashboardData(window);

  const windowLabel = STATS_WINDOW_LABELS[window];
  const overviewData = overview.data;
  const showMetricSkeletons = overview.isLoading && overviewData === null;
  const isChartEmpty =
    timeseries.data?.buckets.every(
      (bucket) => bucket.allow + bucket.deny + bucket.monitor === 0,
    ) ?? false;

  const ruleItems: TopListItem[] = (top.data?.rules ?? []).map((rule) => ({
    id: String(rule.rule_id),
    label: String(rule.rule_id),
    caption: rule.rule_message,
    count: rule.count,
    onSelect: () => navigate(`${appRoutes.logs}?action=deny&rule_id=${rule.rule_id}`),
  }));

  const ipItems: TopListItem[] = (top.data?.source_ips ?? []).map((entry) => ({
    id: entry.source_ip,
    label: entry.source_ip,
    count: entry.count,
    badge: entry.is_banned ? <StatusBadge label="Banned" tone="error" /> : null,
    onSelect: () =>
      navigate(
        `${appRoutes.logs}?action=deny&source_ip=${encodeURIComponent(entry.source_ip)}`,
      ),
  }));

  return (
    <section className="space-y-4">
      <PageHeader
        title="Security operations"
        description={`Traffic, threats and deployment state over the last ${windowLabel}.`}
        actions={
          <>
            <TimeRangeTabs value={window} onChange={setWindow} />
            <Button
              variant="outline"
              size="sm"
              onClick={refresh}
              className="cursor-pointer gap-2"
            >
              <RefreshCw aria-hidden="true" />
              Refresh
            </Button>
          </>
        }
      />

      {lastUpdatedAt ? (
        <p className="text-xs text-muted-foreground">
          Updated {lastUpdatedAt.toLocaleTimeString()} · auto-refreshes every 30s
        </p>
      ) : null}

      <div className="grid gap-4 xl:grid-cols-12">
        {/* Hero: the one block that should catch the eye first. */}
        <Card
          as="article"
          className="flex flex-col gap-5 bg-gradient-to-b from-card to-background p-6 xl:col-span-8"
        >
          <div className="flex flex-wrap items-start justify-between gap-4">
            <div>
              <h2 className="text-sm font-medium tracking-wide text-muted-foreground uppercase">
                Threat activity
              </h2>
              <p className="tabular-figures mt-1 font-mono text-4xl leading-none font-semibold text-foreground">
                {overviewData ? formatCount(overviewData.requests.current) : "—"}
                <span className="ml-2 font-sans text-sm font-normal text-muted-foreground">
                  requests
                </span>
              </p>
            </div>
            <ActivityChartLegend />
          </div>

          {timeseries.error ? (
            <ErrorState title="Could not load activity" description={timeseries.error} />
          ) : timeseries.isLoading && timeseries.data === null ? (
            <div
              className="h-40 animate-pulse rounded-md bg-muted sm:h-52"
              role="status"
              aria-label="Loading activity chart"
            />
          ) : isChartEmpty ? (
            <EmptyState
              title={`No traffic in the last ${windowLabel}`}
              description="Once a protected vhost starts receiving requests, activity will appear here."
              action={
                <Link
                  to={appRoutes.vhosts}
                  className="flex items-center gap-1 text-sm font-medium text-primary hover:opacity-80"
                >
                  Manage vhosts
                  <ArrowRight aria-hidden="true" className="h-4 w-4" />
                </Link>
              }
            />
          ) : timeseries.data ? (
            <ActivityChart
              buckets={timeseries.data.buckets}
              bucketSeconds={timeseries.data.bucket_seconds}
            />
          ) : null}

          {overview.error ? (
            <ErrorState title="Could not load metrics" description={overview.error} />
          ) : (
            <div
              className={
                isAdmin
                  ? "grid gap-3 sm:grid-cols-2 lg:grid-cols-4"
                  : "grid gap-3 sm:grid-cols-3"
              }
            >
              <MetricTile
                label="Blocked"
                metric={overviewData?.blocked ?? null}
                tone="error"
                icon={<AlertTriangleIcon />}
                deltaMeaning="increase-is-bad"
                isLoading={showMetricSkeletons}
              />
              <MetricTile
                label="Critical"
                metric={overviewData?.critical ?? null}
                tone="error"
                icon={<PulseIcon />}
                deltaMeaning="increase-is-bad"
                isLoading={showMetricSkeletons}
              />
              <MetricTile
                label="Monitored"
                metric={overviewData?.monitored ?? null}
                tone="warning"
                icon={<ServerIcon />}
                deltaMeaning="neutral"
                isLoading={showMetricSkeletons}
              />
              {isAdmin ? (
                <MetricTile
                  label="Banned IPs"
                  metric={null}
                  value={overviewData?.banned_ips ?? null}
                  hint={
                    overviewData && overviewData.banned_ips === null
                      ? "Runtime API unavailable"
                      : "currently blocked at the edge"
                  }
                  tone="error"
                  icon={<BanIcon />}
                  isLoading={showMetricSkeletons}
                />
              ) : null}
            </div>
          )}
        </Card>

        <div className="xl:col-span-4">
          <SystemStatusCard status={runtimeStatus} overview={overviewData} />
        </div>
      </div>

      <div className="grid gap-4 xl:grid-cols-12">
        <div className="xl:col-span-4">
          <SectionCard
            title="Top rules"
            description={`Most frequently triggered over the last ${windowLabel}.`}
            descriptionDisplay="tooltip"
          >
            <TopThreats
              isLoading={top.isLoading && top.data === null}
              error={top.error}
              items={ruleItems}
              unitLabel="denied requests"
              emptyTitle="No rules triggered"
              emptyDescription="Nothing has been blocked in this window."
            />
          </SectionCard>
        </div>

        <div className="xl:col-span-4">
          <SectionCard
            title="Top source IPs"
            description={`Most denied requests over the last ${windowLabel}.`}
            descriptionDisplay="tooltip"
            actions={
              isAdmin ? (
                <Link
                  to={appRoutes.bannedIps}
                  className="flex items-center gap-1 text-sm font-medium text-primary transition-opacity duration-150 hover:opacity-80"
                >
                  Ban list
                  <ArrowRight aria-hidden="true" className="h-4 w-4" />
                </Link>
              ) : null
            }
          >
            <TopThreats
              isLoading={top.isLoading && top.data === null}
              error={top.error}
              items={ipItems}
              unitLabel="denied requests"
              emptyTitle="No blocked sources"
              emptyDescription="No client has been denied in this window."
            />
          </SectionCard>
        </div>

        <div className="xl:col-span-4">
          <RecentBlocksCard blocks={recentBlocks} />
        </div>
      </div>
    </section>
  );
}

type TopThreatsProps = {
  isLoading: boolean;
  error: string | null;
  items: TopListItem[];
  unitLabel: string;
  emptyTitle: string;
  emptyDescription: string;
};

function TopThreats({
  isLoading,
  error,
  items,
  unitLabel,
  emptyTitle,
  emptyDescription,
}: TopThreatsProps) {
  if (error) {
    return <ErrorState title="Could not load data" description={error} />;
  }
  if (isLoading) {
    return (
      <div className="space-y-3" role="status" aria-label="Loading">
        {[0, 1, 2, 3, 4].map((row) => (
          <div key={row} className="h-10 animate-pulse rounded-md bg-muted" />
        ))}
      </div>
    );
  }
  if (items.length === 0) {
    return <EmptyState title={emptyTitle} description={emptyDescription} />;
  }
  return <TopList items={items} unitLabel={unitLabel} />;
}
