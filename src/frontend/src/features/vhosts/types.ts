export type VHost = {
  id: number;
  domain: string;
  backend_url: string;
  description: string | null;
  ssl_enabled: boolean;
  is_active: boolean;
  policy_id: number | null;
  created_by: number;
  created_at: string;
  updated_at: string;
};

export type VHostCreate = {
  domain: string;
  backend_url: string;
  description?: string | null;
  ssl_enabled?: boolean;
  is_active?: boolean;
  policy_id?: number | null;
};

export type VHostUpdate = {
  domain?: string;
  backend_url?: string;
  description?: string | null;
  ssl_enabled?: boolean;
  is_active?: boolean;
  policy_id?: number | null;
};

export type Policy = {
  id: number;
  name: string;
};
