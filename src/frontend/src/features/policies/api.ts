import { apiRequest } from "@/lib/api-client";

import type {
  CustomRule,
  CustomRuleCreate,
  CustomRuleUpdate,
  Policy,
  PolicyCreate,
  PolicyDetail,
  PolicyUpdate,
  RuleExclusion,
  RuleExclusionCreate,
  RuleExclusionUpdate,
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

export function listRuleExclusions(
  token: string,
  policyId: number,
  signal?: AbortSignal,
) {
  return apiRequest<RuleExclusion[]>(`/policies/${policyId}/exclusions`, {
    token,
    signal,
  });
}

export function createRuleExclusion(
  token: string,
  policyId: number,
  body: RuleExclusionCreate,
) {
  return apiRequest<RuleExclusion>(`/policies/${policyId}/exclusions`, {
    method: "POST",
    token,
    body,
  });
}

export function updateRuleExclusion(
  token: string,
  policyId: number,
  ruleExclusionId: number,
  body: RuleExclusionUpdate,
) {
  return apiRequest<RuleExclusion>(
    `/policies/${policyId}/exclusions/${ruleExclusionId}`,
    {
      method: "PATCH",
      token,
      body,
    },
  );
}

export function deleteRuleExclusion(
  token: string,
  policyId: number,
  ruleExclusionId: number,
) {
  return apiRequest<void>(
    `/policies/${policyId}/exclusions/${ruleExclusionId}`,
    {
      method: "DELETE",
      token,
      responseType: "empty",
    },
  );
}

export function listCustomRules(
  token: string,
  policyId: number,
  signal?: AbortSignal,
) {
  return apiRequest<CustomRule[]>(`/policies/${policyId}/custom-rules`, {
    token,
    signal,
  });
}

export function createCustomRule(
  token: string,
  policyId: number,
  body: CustomRuleCreate,
) {
  return apiRequest<CustomRule>(`/policies/${policyId}/custom-rules`, {
    method: "POST",
    token,
    body,
  });
}

export function updateCustomRule(
  token: string,
  policyId: number,
  customRuleId: number,
  body: CustomRuleUpdate,
) {
  return apiRequest<CustomRule>(
    `/policies/${policyId}/custom-rules/${customRuleId}`,
    {
      method: "PATCH",
      token,
      body,
    },
  );
}

export function deleteCustomRule(
  token: string,
  policyId: number,
  customRuleId: number,
) {
  return apiRequest<void>(
    `/policies/${policyId}/custom-rules/${customRuleId}`,
    {
      method: "DELETE",
      token,
      responseType: "empty",
    },
  );
}
