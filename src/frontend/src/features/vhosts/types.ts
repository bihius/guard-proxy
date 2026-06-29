export type VHostBackend = {
  id: number;
  vhost_id: number;
  url: string;
  is_active: boolean;
  health_check_enabled: boolean;
  health_check_path: string;
  health_check_interval_seconds: number;
  health_check_fall: number;
  health_check_rise: number;
  created_at: string;
  updated_at: string;
};

export type VHostBackendInput = {
  url: string;
  is_active: boolean;
  health_check_enabled: boolean;
  health_check_path: string;
  health_check_interval_seconds: number;
  health_check_fall: number;
  health_check_rise: number;
};

export type VHost = {
  id: number;
  domain: string;
  backend_url: string;
  backends: VHostBackend[];
  description: string | null;
  ssl_enabled: boolean;
  ssl_provider: "none" | "upload" | "letsencrypt";
  ssl_expires_at: string | null;
  is_active: boolean;
  policy_id: number | null;
  created_by: number | null;
  created_at: string;
  updated_at: string;
};

export type VHostListResponse = {
  items: VHost[];
  total: number;
  page: number;
  per_page: number;
};

export type VHostAssignedPolicy = {
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

export type VHostDetail = VHost & {
  policy: VHostAssignedPolicy | null;
};

export type VHostCreate = {
  domain: string;
  backend_url?: string | null;
  backends?: VHostBackendInput[];
  description?: string | null;
  ssl_enabled?: boolean;
  ssl_provider?: "none" | "upload" | "letsencrypt";
  ssl_cert?: string | null;
  ssl_key?: string | null;
  is_active?: boolean;
  policy_id?: number | null;
};

export type VHostUpdate = {
  domain?: string;
  backend_url?: string | null;
  backends?: VHostBackendInput[];
  description?: string | null;
  ssl_enabled?: boolean;
  ssl_provider?: "none" | "upload" | "letsencrypt";
  ssl_cert?: string | null;
  ssl_key?: string | null;
  is_active?: boolean;
  policy_id?: number | null;
};

export type Policy = {
  id: number;
  name: string;
};

export type PolicyListResponse = {
  items: Policy[];
  total: number;
  page: number;
  per_page: number;
};
