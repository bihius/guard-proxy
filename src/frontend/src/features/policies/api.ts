import { apiRequest } from "@/lib/api-client";

import type { Policy, PolicyCreate, PolicyDetail, PolicyUpdate } from "./types";

export function listPolicies(token: string, signal?: AbortSignal) {
  return apiRequest<Policy[]>("/policies", { token, signal });
}

export function getPolicy(token: string, id: number, signal?: AbortSignal) {
  return apiRequest<PolicyDetail>(`/policies/${id}`, { token, signal });
}

export function createPolicy(token: string, body: PolicyCreate) {
  return apiRequest<Policy>("/policies", { method: "POST", token, body });
}

export function updatePolicy(token: string, id: number, body: PolicyUpdate) {
  return apiRequest<Policy>(`/policies/${id}`, { method: "PATCH", token, body });
}

export function deletePolicy(token: string, id: number) {
  return apiRequest<void>(`/policies/${id}`, {
    method: "DELETE",
    token,
    responseType: "empty",
  });
}
