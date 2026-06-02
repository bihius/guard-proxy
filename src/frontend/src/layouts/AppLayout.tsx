import { Outlet } from "react-router-dom";

import { NavBar } from "@/components/layout/NavBar";

export function AppLayout() {
  return (
    <div className="min-h-screen bg-app text-foreground">
      <NavBar />
      <main className="mx-auto max-w-7xl px-6 py-8 lg:px-10">
        <Outlet />
      </main>
    </div>
  );
}
