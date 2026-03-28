import { Outlet } from "react-router-dom";

import { NavBar } from "@/components/layout/NavBar";

export function AppLayout() {
  return (
    <div className="min-h-screen bg-app text-[var(--color-fg)]">
      <NavBar />
      <main className="mx-auto max-w-[1400px] px-4 py-8 sm:px-6 lg:px-8">
        <Outlet />
      </main>
    </div>
  );
}
