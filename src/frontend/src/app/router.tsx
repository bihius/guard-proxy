import { createBrowserRouter, Navigate } from "react-router-dom";

import {
  ProtectedRoute,
  PublicOnlyRoute,
} from "@/features/auth/protected-route";
import { AppLayout } from "@/layouts/AppLayout";
import { DashboardPage } from "@/pages/dashboard/DashboardPage";
import { ForbiddenPage } from "@/pages/forbidden/ForbiddenPage";
import { LoginPage } from "@/pages/login/LoginPage";
import { PoliciesPage } from "@/pages/policies/PoliciesPage";
import { VHostDetailPage } from "@/pages/vhosts/VHostDetailPage";
import { VHostsPage } from "@/pages/vhosts/VHostsPage";

export const router = createBrowserRouter([
  {
    element: <PublicOnlyRoute />,
    children: [
      {
        path: "/login",
        element: <LoginPage />,
      },
    ],
  },
  {
    element: <ProtectedRoute />,
    children: [
      {
        path: "/",
        element: <AppLayout />,
        children: [
          {
            index: true,
            element: <Navigate to="/dashboard" replace />,
          },
          {
            path: "dashboard",
            element: <DashboardPage />,
          },
          {
            path: "forbidden",
            element: <ForbiddenPage />,
          },
          {
            path: "vhosts",
            element: <VHostsPage />,
          },
          {
            path: "vhosts/:vhostId",
            element: <VHostDetailPage />,
          },
          {
            path: "policies",
            element: <PoliciesPage />,
          },
        ],
      },
    ],
  },
]);
