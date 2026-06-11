export type VHost = {
  id: number;
  domain: string;
  backend_url: string;
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
  backend_url: string;
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
  backend_url?: string;
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
