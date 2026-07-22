import { createBrowserRouter, Navigate } from "react-router-dom";

import { appRoutes } from "@/app/routes";
import { ProtectedRoute, PublicOnlyRoute } from "@/features/auth/protected-route";
import { AppLayout } from "@/layouts/AppLayout";
import { BannedIpsPage } from "@/pages/banned-ips/BannedIpsPage";
import { DashboardPage } from "@/pages/dashboard/DashboardPage";
import { ForbiddenPage } from "@/pages/forbidden/ForbiddenPage";
import { LoginPage } from "@/pages/login/LoginPage";
import { NotFoundPage } from "@/pages/not-found/NotFoundPage";
import { PoliciesPage } from "@/pages/policies/PoliciesPage";
import { PolicyDetailPage } from "@/pages/policies/PolicyDetailPage";
import { LogsPage } from "@/pages/logs/LogsPage";
import { VHostDetailPage } from "@/pages/vhosts/VHostDetailPage";
import { VHostsPage } from "@/pages/vhosts/VHostsPage";

export const router = createBrowserRouter([
  {
    element: <PublicOnlyRoute />,
    children: [
      {
        path: appRoutes.login,
        element: <LoginPage />,
      },
    ],
  },
  {
    element: <ProtectedRoute />,
    children: [
      {
        path: appRoutes.root,
        element: <AppLayout />,
        children: [
          {
            index: true,
            element: <Navigate to={appRoutes.dashboard} replace />,
          },
          {
            path: appRoutes.dashboard,
            element: <DashboardPage />,
          },
          {
            path: appRoutes.forbidden,
            element: <ForbiddenPage />,
          },
          {
            path: appRoutes.vhosts,
            element: <VHostsPage />,
          },
          {
            path: `${appRoutes.vhosts}/:vhostId`,
            element: <VHostDetailPage />,
          },
          {
            path: appRoutes.policies,
            element: <PoliciesPage />,
          },
          {
            path: `${appRoutes.policies}/:policyId`,
            element: <PolicyDetailPage />,
          },
          {
            path: appRoutes.logs,
            element: <LogsPage />,
          },
          {
            path: appRoutes.bannedIps,
            element: <BannedIpsPage />,
          },
        ],
      },
    ],
  },
  {
    path: "*",
    element: <NotFoundPage />,
  },
]);
