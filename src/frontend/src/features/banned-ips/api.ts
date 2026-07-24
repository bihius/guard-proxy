import { apiRequest } from "@/lib/api-client";

import type { BannedIpListResponse, UnbanResponse } from "./types";

export function listBannedIps(token: string, signal?: AbortSignal) {
  return apiRequest<BannedIpListResponse>("/security/banned-ips", { token, signal });
}

export function unbanIp(token: string, ip: string) {
  return apiRequest<UnbanResponse>(`/security/banned-ips/${encodeURIComponent(ip)}`, {
    method: "DELETE",
    token,
  });
}
