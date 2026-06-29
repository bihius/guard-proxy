import { apiRequest } from "@/lib/api-client";

import type {
  Policy,
  PolicyListResponse,
  VHost,
  VHostCreate,
  VHostDetail,
  VHostListResponse,
  VHostUpdate,
} from "./types";

export type ListVHostsParams = {
  page?: number;
  per_page?: number;
  q?: string;
};

export type ListPoliciesParams = {
  page?: number;
  per_page?: number;
  q?: string;
};

function withQuery(path: string, params: ListVHostsParams | ListPoliciesParams) {
  const query = new URLSearchParams();

  for (const [key, value] of Object.entries(params)) {
    if (value === undefined || value === null || value === "") continue;
    query.set(key, String(value));
  }

  const queryString = query.toString();
  return queryString ? `${path}?${queryString}` : path;
}

export function listVHosts(
  token: string,
  params: ListVHostsParams = {},
  signal?: AbortSignal,
) {
  return apiRequest<VHostListResponse>(withQuery("/vhosts", params), { token, signal });
}

export async function listAllVHosts(token: string, signal?: AbortSignal) {
  const perPage = 500;
  let page = 1;
  const items: VHost[] = [];

  while (true) {
    const response = await listVHosts(token, { page, per_page: perPage }, signal);
    items.push(...response.items);

    if (items.length >= response.total || response.items.length === 0) {
      return items;
    }

    page += 1;
  }
}

export function getVHost(token: string, id: number, signal?: AbortSignal) {
  return apiRequest<VHostDetail>(`/vhosts/${id}`, { token, signal });
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

export function listPolicies(
  token: string,
  params: ListPoliciesParams = {},
  signal?: AbortSignal,
) {
  return apiRequest<PolicyListResponse>(withQuery("/policies", params), { token, signal });
}

export async function listAllPolicies(token: string, signal?: AbortSignal) {
  const perPage = 500;
  let page = 1;
  const items: Policy[] = [];

  while (true) {
    const response = await listPolicies(token, { page, per_page: perPage }, signal);
    items.push(...response.items);

    if (items.length >= response.total || response.items.length === 0) {
      return items;
    }

    page += 1;
  }
}
