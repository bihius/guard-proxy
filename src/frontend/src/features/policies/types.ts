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

export type PolicyDetail = Policy & {
  rule_overrides: RuleOverride[];
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
