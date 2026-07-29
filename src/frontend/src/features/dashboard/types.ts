/** Mirrors `src/backend/app/schemas/stats.py`. */

export const STATS_WINDOWS = ["1h", "24h", "7d", "30d"] as const;

export type StatsWindow = (typeof STATS_WINDOWS)[number];

export const STATS_WINDOW_LABELS: Record<StatsWindow, string> = {
  "1h": "1 hour",
  "24h": "24 hours",
  "7d": "7 days",
  "30d": "30 days",
};

export function isStatsWindow(value: string | null): value is StatsWindow {
  return value !== null && (STATS_WINDOWS as readonly string[]).includes(value);
}

export type MetricValue = {
  current: number;
  previous: number;
  /** null when the previous window was empty — there is no baseline to compare to. */
  delta_pct: number | null;
};

type WindowBounds = {
  window: StatsWindow;
  start_at: string;
  end_at: string;
};

export type OverviewResponse = WindowBounds & {
  requests: MetricValue;
  blocked: MetricValue;
  monitored: MetricValue;
  critical: MetricValue;
  /** null for viewers and whenever the HAProxy Runtime API is unreachable. */
  banned_ips: number | null;
  protected_vhosts: number;
  total_vhosts: number;
  active_policies: number;
};

export type TimeseriesBucket = {
  bucket_at: string;
  allow: number;
  deny: number;
  monitor: number;
};

export type TimeseriesResponse = WindowBounds & {
  bucket_seconds: number;
  buckets: TimeseriesBucket[];
};

export type TopRule = {
  rule_id: number;
  rule_message: string | null;
  count: number;
};

export type TopSourceIp = {
  source_ip: string;
  count: number;
  is_banned: boolean;
};

export type TopVHost = {
  vhost: string;
  vhost_id: number | null;
  count: number;
};

export type TopResponse = WindowBounds & {
  limit: number;
  rules: TopRule[];
  source_ips: TopSourceIp[];
  vhosts: TopVHost[];
};
