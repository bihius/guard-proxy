import { useLocation } from "react-router-dom";

const pageTitles: Record<string, string> = {
  "/dashboard": "Dashboard",
  "/vhosts": "VHosts",
  "/policies": "Policies",
};

export function Topbar() {
  const location = useLocation();
  const title =
    location.pathname.startsWith("/vhosts/") && location.pathname !== "/vhosts"
      ? "VHost Detail"
      : pageTitles[location.pathname] ?? "Guard Proxy";

  return (
    <header className="border-b border-slate-800/90 bg-slate-950/60 px-6 py-4 backdrop-blur sm:px-8 lg:px-10">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.2em] text-slate-500">
            Admin Panel
          </p>
          <h2 className="mt-2 text-2xl font-semibold tracking-tight text-slate-50">
            {title}
          </h2>
        </div>

        <div className="flex items-center gap-3">
          <span className="rounded-full border border-emerald-500/30 bg-emerald-500/10 px-3 py-1 text-xs font-semibold uppercase tracking-[0.18em] text-emerald-300">
            Dev Mode
          </span>
          <span className="rounded-full border border-slate-700 bg-slate-900 px-3 py-1 text-xs font-semibold uppercase tracking-[0.18em] text-slate-300">
            Role: Unknown
          </span>
        </div>
      </div>
    </header>
  );
}
