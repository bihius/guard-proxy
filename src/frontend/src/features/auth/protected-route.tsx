import { Navigate, Outlet, useLocation } from "react-router-dom";

import { useAuth } from "@/hooks/use-auth";
import type { UserRole } from "@/types/api";

import { AuthPendingState } from "./AuthPendingState";

export function ProtectedRoute() {
  const location = useLocation();
  const { isAuthenticated, isLoading } = useAuth();

  if (isLoading) {
    return <AuthPendingState />;
  }

  if (!isAuthenticated) {
    return <Navigate to="/login" replace state={{ from: location }} />;
  }

  return <Outlet />;
}

export function PublicOnlyRoute() {
  const { isAuthenticated, isLoading } = useAuth();

  if (isLoading) {
    return <AuthPendingState />;
  }

  if (isAuthenticated) {
    return <Navigate to="/dashboard" replace />;
  }

  return <Outlet />;
}

type RoleRouteProps = {
  allow: UserRole | UserRole[];
};

export function RoleRoute({ allow }: RoleRouteProps) {
  const location = useLocation();
  const { hasRole, isLoading } = useAuth();

  if (isLoading) {
    return <AuthPendingState />;
  }

  if (!hasRole(allow)) {
    return <Navigate to="/forbidden" replace state={{ from: location }} />;
  }

  return <Outlet />;
}
