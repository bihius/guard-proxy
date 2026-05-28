import { apiRequest } from "@/lib/api-client";

import type { Policy, VHost, VHostCreate, VHostUpdate } from "./types";

export function listVHosts(token: string, signal?: AbortSignal) {
  return apiRequest<VHost[]>("/vhosts", { token, signal });
}

export function createVHost(token: string, body: VHostCreate) {
  return apiRequest<VHost>("/vhosts", { method: "POST", token, body });
}

export function updateVHost(token: string, id: number, body: VHostUpdate) {
  return apiRequest<VHost>(`/vhosts/${id}`, { method: "PATCH", token, body });
}

export function deleteVHost(token: string, id: number) {
  return apiRequest<void>(`/vhosts/${id}`, {
    method: "DELETE",
    token,
    responseType: "empty",
  });
}

export function listPolicies(token: string, signal?: AbortSignal) {
  return apiRequest<Policy[]>("/policies", { token, signal });
}
