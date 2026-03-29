import type { CurrentUser, LoginRequest, UserRole } from "@/types/api";

export type AuthContextValue = {
  user: CurrentUser | null;
  role: UserRole | null;
  accessToken: string | null;
  refreshToken: string | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  loginError: string | null;
  hasRole: (role: UserRole | UserRole[]) => boolean;
  signIn: (credentials: LoginRequest) => Promise<void>;
  signOut: () => void;
  refreshCurrentUser: () => Promise<void>;
};
