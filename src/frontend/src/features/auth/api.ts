import { apiRequest } from "@/lib/api-client";
import type { CurrentUser, LoginRequest, TokenResponse } from "@/types/api";

export function login(body: LoginRequest, signal?: AbortSignal) {
  return apiRequest<TokenResponse>("/auth/login", {
    method: "POST",
    body,
    credentials: "include",
    signal,
  });
}

export function getCurrentUser(accessToken: string, signal?: AbortSignal) {
  return apiRequest<CurrentUser>("/auth/me", {
    token: accessToken,
    signal,
  });
}

export function refreshSession(signal?: AbortSignal) {
  return apiRequest<TokenResponse>("/auth/refresh", {
    method: "POST",
    credentials: "include",
    signal,
  });
}

export function logout(signal?: AbortSignal) {
  return apiRequest<void>("/auth/logout", {
    method: "POST",
    credentials: "include",
    responseType: "empty",
    signal,
  });
}
