import type { CurrentUser, LoginRequest } from "@/types/api";

export type AuthContextValue = {
  user: CurrentUser | null;
  accessToken: string | null;
  refreshToken: string | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  loginError: string | null;
  signIn: (credentials: LoginRequest) => Promise<void>;
  signOut: () => void;
  refreshCurrentUser: () => Promise<void>;
};
