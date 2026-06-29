export type Policy = {
  id: number;
  name: string;
  description: string | null;
  paranoia_level: 1 | 2 | 3 | 4;
  inbound_anomaly_threshold: number;
  outbound_anomaly_threshold: number;
  enforcement_mode: "block" | "detect_only";
  is_active: boolean;
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
  | "args"
  | "args_names"
  | "request_headers";

export type RuleExclusion = {
  id: number;
  policy_id: number;
  rule_id: number;
  target_type: RuleExclusionTargetType;
  target_value: string;
  scope_path: string | null;
  comment: string | null;
  created_at: string;
};

export type RuleExclusionCreate = {
  rule_id: number;
  target_type: RuleExclusionTargetType;
  target_value: string;
  scope_path?: string | null;
  comment?: string | null;
};

export type RuleExclusionUpdate = {
  rule_id?: number;
  target_type?: RuleExclusionTargetType;
  target_value?: string;
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
};

export type PolicyUpdate = {
  name?: string;
  description?: string | null;
  paranoia_level?: 1 | 2 | 3 | 4;
  inbound_anomaly_threshold?: number;
  outbound_anomaly_threshold?: number;
  enforcement_mode?: "block" | "detect_only";
  is_active?: boolean;
};
