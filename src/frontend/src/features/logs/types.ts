export type LogAction = "allow" | "deny" | "monitor";
export type LogSeverity = "info" | "warning" | "error" | "critical";

export type Log = {
  id: number;
  producer_event_id: string | null;
  event_at: string;
  vhost: string;
  action: LogAction;
  source_ip: string;
  method: string;
  request_uri: string;
  status_code: number | null;
  rule_id: number | null;
  rule_message: string | null;
  anomaly_score: number | null;
  paranoia_level: number | null;
  severity: LogSeverity;
  message: string | null;
  raw_context: Record<string, unknown> | null;
  vhost_id: number | null;
  policy_id: number | null;
};

export type LogListResponse = {
  items: Log[];
  total: number;
  page: number;
  page_size: number;
};

export type LogFilters = {
  vhost: string;
  action: LogAction | "";
  policy_id: number | null;
  date_from: string;
  date_to: string;
};

export const EMPTY_FILTERS: LogFilters = {
  vhost: "",
  action: "",
  policy_id: null,
  date_from: "",
  date_to: "",
};
