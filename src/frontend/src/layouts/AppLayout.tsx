import { Outlet } from "react-router-dom";

import { NavBar } from "@/components/layout/NavBar";
import { ApplyNoticeProvider } from "@/features/runtime/apply-notice";
import { ConfigChangedProvider } from "@/features/runtime/config-changed-provider";

export function AppLayout() {
  return (
    <ConfigChangedProvider>
      <ApplyNoticeProvider>
        <div className="min-h-screen bg-app text-foreground">
          <NavBar />
          <main className="mx-auto max-w-[96rem] px-6 py-8 lg:px-10">
            <Outlet />
          </main>
        </div>
      </ApplyNoticeProvider>
    </ConfigChangedProvider>
  );
}
