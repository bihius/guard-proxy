import { apiRequest } from "@/lib/api-client";
import type { CurrentUser, LoginRequest, TokenResponse } from "@/types/api";

export function login(body: LoginRequest) {
  return apiRequest<TokenResponse>("/auth/login", {
    method: "POST",
    body,
    credentials: "include",
  });
}

export function getCurrentUser(accessToken: string) {
  return apiRequest<CurrentUser>("/auth/me", {
    token: accessToken,
  });
}

export function refreshSession() {
  return apiRequest<TokenResponse>("/auth/refresh", {
    method: "POST",
    credentials: "include",
  });
}

export function logout() {
  return apiRequest<void>("/auth/logout", {
    method: "POST",
    credentials: "include",
    responseType: "empty",
  });
}
