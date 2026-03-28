import { createBrowserRouter, Navigate } from "react-router-dom";

import { AppLayout } from "@/layouts/AppLayout";
import { DashboardPage } from "@/pages/dashboard/DashboardPage";
import { LoginPage } from "@/pages/login/LoginPage";
import { PoliciesPage } from "@/pages/policies/PoliciesPage";
import { VHostDetailPage } from "@/pages/vhosts/VHostDetailPage";
import { VHostsPage } from "@/pages/vhosts/VHostsPage";

export const router = createBrowserRouter([
  {
    path: "/",
    element: <Navigate to="/dashboard" replace />,
  },
  {
    path: "/login",
    element: <LoginPage />,
  },
  {
    path: "/",
    element: <AppLayout />,
    children: [
      {
        path: "/dashboard",
        element: <DashboardPage />,
      },
      {
        path: "/vhosts",
        element: <VHostsPage />,
      },
      {
        path: "/vhosts/:vhostId",
        element: <VHostDetailPage />,
      },
      {
        path: "/policies",
        element: <PoliciesPage />,
      },
    ],
  },
]);
