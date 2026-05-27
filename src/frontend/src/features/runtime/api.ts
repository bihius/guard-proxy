import { apiRequest } from "@/lib/api-client";

import type { ConfigApplyResponse, RuntimeStatusResponse } from "./types";

export function applyConfig(accessToken: string, signal?: AbortSignal) {
  return apiRequest<ConfigApplyResponse>("/config/apply", {
    method: "POST",
    token: accessToken,
    signal,
  });
}

export function getRuntimeStatus(accessToken: string, signal?: AbortSignal) {
  return apiRequest<RuntimeStatusResponse>("/runtime/status", {
    token: accessToken,
    signal,
  });
}
