import { apiRequest } from "@/lib/api-client";
import type { CurrentUser, LoginRequest, TokenResponse } from "@/types/api";

export function login(body: LoginRequest) {
  return apiRequest<TokenResponse>("/auth/login", {
    method: "POST",
    body,
  });
}

export function getCurrentUser(accessToken: string) {
  return apiRequest<CurrentUser>("/auth/me", {
    token: accessToken,
  });
}
