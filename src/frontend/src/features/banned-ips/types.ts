export type BannedIp = {
  ip: string;
  vhost_id: number;
  domain: string;
  gpc0: number;
  ban_threshold: number;
  banned: boolean;
  expires_in_seconds: number;
};

export type BannedIpListResponse = {
  items: BannedIp[];
  total: number;
};

export type UnbanResponse = {
  ip: string;
  cleared: number;
};
