export type GeoipMode = "off" | "allowlist" | "blocklist";

export type Policy = {
  id: number;
  name: string;
  description: string | null;
  paranoia_level: 1 | 2 | 3 | 4;
  inbound_anomaly_threshold: number;
  outbound_anomaly_threshold: number;
  enforcement_mode: "block" | "detect_only";
  is_active: boolean;
  ddos_protection_enabled: boolean;
  rate_limit_requests: number;
  rate_limit_window_seconds: number;
  max_connections_per_ip: number;
  auto_ban_enabled: boolean;
  ban_threshold: number;
  ban_duration_seconds: number;
  geoip_mode: GeoipMode;
  geoip_countries: string[];
  created_by: number | null;
  created_at: string;
  updated_at: string;
};

export type PolicyListResponse = {
  items: Policy[];
  total: number;
  page: number;
  per_page: number;
};

export type RuleOverride = {
  id: number;
  policy_id: number;
  rule_id: number;
  action: "enable" | "disable";
  comment: string | null;
  created_at: string;
};

export type RuleOverrideCreate = {
  rule_id: number;
  action: "enable" | "disable";
  comment?: string | null;
};

export type RuleOverrideUpdate = {
  rule_id?: number;
  action?: "enable" | "disable";
  comment?: string | null;
};

export type RuleExclusionTargetType =
  | "request_uri"
  | "request_uri_raw"
  | "request_filename"
  | "args"
  | "args_names"
  | "request_headers"
  | "request_headers_names"
  | "request_cookies"
  | "request_cookies_names";

export type RuleExclusion = {
  id: number;
  policy_id: number;
  rule_id: number;
  target_type: RuleExclusionTargetType;
  target_value: string | null;
  scope_path: string | null;
  comment: string | null;
  created_at: string;
};

export type RuleExclusionCreate = {
  rule_id: number;
  target_type: RuleExclusionTargetType;
  target_value: string | null;
  scope_path?: string | null;
  comment?: string | null;
};

/** Draft exclusion derived from a WAF event (POST /logs/{id}/suggest-exclusion). */
export type RuleExclusionSuggestion = {
  policy_id: number;
  rule_id: number;
  target_type: RuleExclusionTargetType | null;
  target_value: string | null;
  scope_path: string | null;
  comment: string;
  /** What Coraza matched, e.g. "ARGS:q"; set even when it is not a valid target. */
  matched_variable: string | null;
};

/** Learning mode: an exclusion proposed from repeated rule matches (#263). */
export type TuningSuggestion = {
  id: number;
  policy_id: number;
  rule_id: number;
  rule_message: string | null;
  target_type: RuleExclusionTargetType;
  target_value: string | null;
  scope_path: string | null;
  /** 0-100 heuristic likelihood that the matches are false positives. */
  confidence: number;
  event_count: number;
  source_ip_count: number;
  first_seen_at: string;
  last_seen_at: string;
  sample_log_ids: number[];
  status: "pending" | "approved" | "rejected";
  rule_exclusion_id: number | null;
  created_at: string;
  updated_at: string;
  resolved_at: string | null;
};

export type TuningAnalysis = {
  events_scanned: number;
  created: number;
  updated: number;
  window_hours: number;
};

export type RuleExclusionUpdate = {
  rule_id?: number;
  target_type?: RuleExclusionTargetType;
  target_value?: string | null;
  scope_path?: string | null;
  comment?: string | null;
};

export type CustomRulePhase =
  | "request_headers"
  | "request_body";

export type CustomRuleOperator =
  | "rx"
  | "streq"
  | "contains"
  | "begins_with"
  | "ends_with"
  | "eq"
  | "ge"
  | "gt"
  | "le"
  | "lt"
  | "pm"
  | "within"
  | "ip_match";

export const CUSTOM_RULE_ID_MIN = 9000000;
export const CUSTOM_RULE_ID_MAX = 9099999;

export type CustomRule = {
  id: number;
  policy_id: number;
  rule_id: number;
  phase: CustomRulePhase;
  variables: string;
  operator: CustomRuleOperator;
  operator_argument: string;
  actions: string;
  comment: string | null;
  is_active: boolean;
  created_at: string;
  updated_at: string;
};

export type CustomRuleCreate = {
  rule_id: number;
  phase: CustomRulePhase;
  variables: string;
  operator: CustomRuleOperator;
  operator_argument: string;
  actions: string;
  comment?: string | null;
  is_active?: boolean;
};

export type CustomRuleUpdate = {
  rule_id?: number;
  phase?: CustomRulePhase;
  variables?: string;
  operator?: CustomRuleOperator;
  operator_argument?: string;
  actions?: string;
  comment?: string | null;
  is_active?: boolean;
};

export type PolicyDetail = Policy & {
  rule_overrides: RuleOverride[];
  rule_exclusions: RuleExclusion[];
  custom_rules: CustomRule[];
};

export type PolicyCreate = {
  name: string;
  description?: string | null;
  paranoia_level?: 1 | 2 | 3 | 4;
  inbound_anomaly_threshold?: number;
  outbound_anomaly_threshold?: number;
  enforcement_mode?: "block" | "detect_only";
  ddos_protection_enabled?: boolean;
  rate_limit_requests?: number;
  rate_limit_window_seconds?: number;
  max_connections_per_ip?: number;
  auto_ban_enabled?: boolean;
  ban_threshold?: number;
  ban_duration_seconds?: number;
  geoip_mode?: GeoipMode;
  geoip_countries?: string[];
};

export type PolicyUpdate = {
  name?: string;
  description?: string | null;
  paranoia_level?: 1 | 2 | 3 | 4;
  inbound_anomaly_threshold?: number;
  outbound_anomaly_threshold?: number;
  enforcement_mode?: "block" | "detect_only";
  is_active?: boolean;
  ddos_protection_enabled?: boolean;
  rate_limit_requests?: number;
  rate_limit_window_seconds?: number;
  max_connections_per_ip?: number;
  auto_ban_enabled?: boolean;
  ban_threshold?: number;
  ban_duration_seconds?: number;
  geoip_mode?: GeoipMode;
  geoip_countries?: string[];
};
