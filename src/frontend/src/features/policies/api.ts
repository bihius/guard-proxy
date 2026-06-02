import { apiRequest } from "@/lib/api-client";

import type {
  Policy,
  PolicyCreate,
  PolicyDetail,
  PolicyUpdate,
  RuleOverride,
  RuleOverrideCreate,
  RuleOverrideUpdate,
} from "./types";

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

export function listRuleOverrides(
  token: string,
  policyId: number,
  signal?: AbortSignal,
) {
  return apiRequest<RuleOverride[]>(`/policies/${policyId}/rules`, {
    token,
    signal,
  });
}

export function createRuleOverride(
  token: string,
  policyId: number,
  body: RuleOverrideCreate,
) {
  return apiRequest<RuleOverride>(`/policies/${policyId}/rules`, {
    method: "POST",
    token,
    body,
  });
}

export function updateRuleOverride(
  token: string,
  policyId: number,
  ruleOverrideId: number,
  body: RuleOverrideUpdate,
) {
  return apiRequest<RuleOverride>(
    `/policies/${policyId}/rules/${ruleOverrideId}`,
    {
      method: "PATCH",
      token,
      body,
    },
  );
}

export function deleteRuleOverride(
  token: string,
  policyId: number,
  ruleOverrideId: number,
) {
  return apiRequest<void>(`/policies/${policyId}/rules/${ruleOverrideId}`, {
    method: "DELETE",
    token,
    responseType: "empty",
  });
}
