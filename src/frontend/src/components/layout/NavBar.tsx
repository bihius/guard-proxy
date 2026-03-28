import { useState } from "react";
import { NavLink, Link } from "react-router-dom";

const navigation = [
  { to: "/dashboard", label: "Dashboard" },
  { to: "/vhosts", label: "VHosts" },
  { to: "/policies", label: "Policies" },
];

export function NavBar() {
  const [mobileOpen, setMobileOpen] = useState(false);

  return (
    <header className="sticky top-0 z-50 h-14 border-b border-[var(--color-border)] bg-[var(--color-surface)]/80 backdrop-blur-xl">
      <div className="mx-auto flex h-full max-w-[1400px] items-center justify-between px-4 sm:px-6 lg:px-8">
        {/* Logo */}
        <Link to="/dashboard" className="flex items-center gap-2 transition-opacity hover:opacity-80">
          <span className="inline-block h-2.5 w-2.5 rounded-full bg-[var(--color-accent)]" />
          <span className="text-base font-bold tracking-tight text-[var(--color-fg)]">
            Guard Proxy
          </span>
        </Link>

        {/* Desktop nav */}
        <nav className="hidden items-center gap-1 md:flex">
          {navigation.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              className={({ isActive }) =>
                [
                  "rounded-[var(--radius-full)] px-3.5 py-1.5 text-sm font-medium transition-all duration-150",
                  isActive
                    ? "bg-[var(--color-accent-soft)] text-[var(--color-accent)]"
                    : "text-[var(--color-fg-muted)] hover:bg-[var(--color-surface-hover)] hover:text-[var(--color-fg)]",
                ].join(" ")
              }
            >
              {item.label}
            </NavLink>
          ))}
        </nav>

        {/* Right side */}
        <div className="hidden items-center gap-2.5 md:flex">
          <span className="rounded-[var(--radius-full)] bg-[var(--color-accent-soft)] px-3 py-1 text-xs font-semibold text-[var(--color-accent)]">
            Dev Mode
          </span>
          <span className="rounded-[var(--radius-full)] bg-[var(--color-surface-hover)] px-3 py-1 text-xs font-semibold text-[var(--color-fg-muted)]">
            Role: Unknown
          </span>
          <Link
            to="/login"
            className="btn-ghost rounded-[var(--radius-sm)] px-3 py-1.5 text-xs font-semibold"
          >
            Logout
          </Link>
        </div>

        {/* Mobile hamburger */}
        <button
          onClick={() => setMobileOpen(true)}
          className="flex h-9 w-9 items-center justify-center rounded-[var(--radius-sm)] text-[var(--color-fg-muted)] transition hover:bg-[var(--color-surface-hover)] hover:text-[var(--color-fg)] md:hidden"
          aria-label="Open menu"
        >
          <svg width="20" height="20" viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round">
            <line x1="3" y1="5" x2="17" y2="5" />
            <line x1="3" y1="10" x2="17" y2="10" />
            <line x1="3" y1="15" x2="17" y2="15" />
          </svg>
        </button>
      </div>

      {/* Mobile overlay */}
      {mobileOpen && (
        <div className="fixed inset-0 z-50 md:hidden">
          {/* Backdrop */}
          <div
            className="absolute inset-0 bg-black/60 backdrop-blur-sm"
            onClick={() => setMobileOpen(false)}
          />
          {/* Slide-in panel */}
          <nav className="absolute right-0 top-0 flex h-full w-72 flex-col gap-1 border-l border-[var(--color-border)] bg-[var(--color-surface)] p-5 shadow-card-lg">
            <div className="mb-4 flex items-center justify-between">
              <span className="flex items-center gap-2">
                <span className="inline-block h-2.5 w-2.5 rounded-full bg-[var(--color-accent)]" />
                <span className="text-sm font-bold text-[var(--color-fg)]">Guard Proxy</span>
              </span>
              <button
                onClick={() => setMobileOpen(false)}
                className="flex h-8 w-8 items-center justify-center rounded-[var(--radius-sm)] text-[var(--color-fg-muted)] transition hover:bg-[var(--color-surface-hover)] hover:text-[var(--color-fg)]"
                aria-label="Close menu"
              >
                <svg width="18" height="18" viewBox="0 0 18 18" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round">
                  <line x1="4" y1="4" x2="14" y2="14" />
                  <line x1="14" y1="4" x2="4" y2="14" />
                </svg>
              </button>
            </div>

            {navigation.map((item) => (
              <NavLink
                key={item.to}
                to={item.to}
                onClick={() => setMobileOpen(false)}
                className={({ isActive }) =>
                  [
                    "rounded-[var(--radius-md)] px-3.5 py-2.5 text-sm font-medium transition-all",
                    isActive
                      ? "bg-[var(--color-accent-soft)] text-[var(--color-accent)]"
                      : "text-[var(--color-fg-muted)] hover:bg-[var(--color-surface-hover)] hover:text-[var(--color-fg)]",
                  ].join(" ")
                }
              >
                {item.label}
              </NavLink>
            ))}

            <div className="my-3 h-px bg-[var(--color-border)]" />

            <div className="flex flex-wrap gap-2 px-1">
              <span className="rounded-[var(--radius-full)] bg-[var(--color-accent-soft)] px-3 py-1 text-xs font-semibold text-[var(--color-accent)]">
                Dev Mode
              </span>
              <span className="rounded-[var(--radius-full)] bg-[var(--color-surface-hover)] px-3 py-1 text-xs font-semibold text-[var(--color-fg-muted)]">
                Role: Unknown
              </span>
            </div>

            <Link
              to="/login"
              onClick={() => setMobileOpen(false)}
              className="mt-auto btn-ghost rounded-[var(--radius-md)] px-3.5 py-2.5 text-sm font-semibold"
            >
              Logout
            </Link>
          </nav>
        </div>
      )}
    </header>
  );
}
