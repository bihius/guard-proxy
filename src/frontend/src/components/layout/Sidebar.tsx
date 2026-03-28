import { NavLink } from "react-router-dom";

const navigation = [
  { to: "/dashboard", label: "Dashboard" },
  { to: "/vhosts", label: "VHosts" },
  { to: "/policies", label: "Policies" },
  { to: "/login", label: "Logout" },
];

export function Sidebar() {
  return (
    <aside className="border-r border-slate-800/90 bg-slate-950/80 px-4 py-6 backdrop-blur">
      <div className="mb-8 px-3">
        <p className="text-xs font-bold uppercase tracking-[0.22em] text-cyan-400">
          Guard Proxy
        </p>
        <h1 className="mt-3 text-2xl font-semibold tracking-tight text-slate-50">
          Security Admin
        </h1>
        <p className="mt-2 text-sm leading-6 text-slate-400">
          Shared shell for the course team frontend.
        </p>
      </div>

      <nav className="space-y-1">
        {navigation.map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            className={({ isActive }) =>
              [
                "block rounded-2xl px-3 py-2.5 text-sm font-medium transition",
                isActive
                  ? "bg-cyan-500/12 text-cyan-300 ring-1 ring-inset ring-cyan-500/30"
                  : "text-slate-300 hover:bg-slate-900 hover:text-slate-50",
              ].join(" ")
            }
          >
            {item.label}
          </NavLink>
        ))}
      </nav>
    </aside>
  );
}
