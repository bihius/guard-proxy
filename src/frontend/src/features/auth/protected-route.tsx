import { Navigate, Outlet, useLocation } from "react-router-dom";

import { appRoutes } from "@/app/routes";
import { useAuth } from "@/hooks/use-auth";

import { AuthPendingState } from "./AuthPendingState";

export function ProtectedRoute() {
  const location = useLocation();
  const { isAuthenticated, isLoading } = useAuth();

  if (isLoading) {
    return <AuthPendingState />;
  }

  if (!isAuthenticated) {
    return <Navigate to={appRoutes.login} replace state={{ from: location }} />;
  }

  return <Outlet />;
}

export function PublicOnlyRoute() {
  const { isAuthenticated, isLoading } = useAuth();

  if (isLoading) {
    return <AuthPendingState />;
  }

  if (isAuthenticated) {
    return <Navigate to={appRoutes.dashboard} replace />;
  }

  return <Outlet />;
}
