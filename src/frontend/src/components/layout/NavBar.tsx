import { useCallback, useEffect, useState } from "react";
import { Link, NavLink, useNavigate } from "react-router-dom";

import { appRoutes } from "@/app/routes";
import {
  CloseIcon,
  LeafIcon,
  MenuIcon,
  SnowflakeIcon,
} from "@/components/icons";
import { useAuth } from "@/hooks/use-auth";
import { THEMES, type Theme, getThemeStorageKey } from "@/lib/theme";

const navigation = [
  { to: appRoutes.dashboard, label: "Dashboard" },
  { to: appRoutes.vhosts, label: "VHosts" },
  { to: appRoutes.policies, label: "Policies" },
];

function navLinkClass(isActive: boolean, pill = false) {
  return [
    pill
      ? "rounded-[var(--radius-full)] px-3 py-2"
      : "rounded-[var(--radius-md)] px-4 py-2",
    "text-sm font-medium transition-all duration-150",
    isActive
      ? "nav-link-active bg-accent-soft text-accent"
      : "text-fg-muted hover:bg-surface-hover hover:text-fg",
  ].join(" ");
}

function getStoredTheme(): Theme {
  try {
    const stored = localStorage.getItem(getThemeStorageKey());
    if (stored && THEMES.includes(stored as Theme)) {
      return stored as Theme;
    }
  } catch {
    /* privacy mode */
  }

  return (document.documentElement.dataset["theme"] as Theme) ?? "emerald";
}

function applyTheme(theme: Theme) {
  document.documentElement.dataset["theme"] = theme;

  const meta = document.querySelector('meta[name="theme-color"]');
  if (meta) {
    meta.setAttribute("content", theme === "frost" ? "#141a2e" : "#1a2e1a");
  }

  try {
    localStorage.setItem(getThemeStorageKey(), theme);
  } catch {
    /* privacy mode */
  }
}

export function NavBar() {
  const navigate = useNavigate();
  const { signOut, user } = useAuth();
  const [mobileOpen, setMobileOpen] = useState(false);
  const [theme, setTheme] = useState<Theme>(getStoredTheme);

  useEffect(() => {
    applyTheme(theme);
  }, [theme]);

  useEffect(() => {
    if (!mobileOpen) {
      return;
    }

    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        setMobileOpen(false);
      }
    };

    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [mobileOpen]);

  const toggleTheme = useCallback(() => {
    setTheme((currentTheme) =>
      currentTheme === "emerald" ? "frost" : "emerald"
    );
  }, []);

  const handleLogout = useCallback(async () => {
    await signOut();
    setMobileOpen(false);
    navigate(appRoutes.login, {
      replace: true,
    });
  }, [navigate, signOut]);

  return (
    <header className="nav-surface sticky top-0 z-50 h-14 border-b border-border backdrop-blur-xl">
      <div className="flex h-full items-center justify-between px-6 lg:px-10">
        <Link
          to={appRoutes.dashboard}
          className="flex items-center gap-2 transition-opacity hover:opacity-80"
        >
          <span className="inline-block h-2.5 w-2.5 rounded-full bg-accent" />
          <span className="text-base font-bold tracking-tight text-fg">
            Guard Proxy
          </span>
        </Link>

        <nav className="hidden items-center gap-1 md:flex" role="navigation">
          {navigation.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              className={({ isActive }) => navLinkClass(isActive, true)}
            >
              {item.label}
            </NavLink>
          ))}
        </nav>

        <div className="hidden items-center gap-2 md:flex">
          <button
            type="button"
            onClick={toggleTheme}
            className="flex h-8 w-8 items-center justify-center rounded-[var(--radius-sm)] text-fg-muted transition hover:bg-surface-hover hover:text-fg"
            aria-label={`Switch to ${theme === "emerald" ? "frost" : "emerald"} theme`}
            title={`Theme: ${theme}`}
          >
            {theme === "emerald" ? <LeafIcon /> : <SnowflakeIcon />}
          </button>

          <span className="badge-accent rounded-[var(--radius-full)] bg-accent-soft px-4 py-1.5 text-sm font-semibold text-accent">
            Dev Mode
          </span>
          <span className="rounded-[var(--radius-full)] bg-surface-hover px-4 py-1.5 text-sm font-semibold text-fg-muted">
            {user?.full_name || user?.email || "No user"}
          </span>
          <button
            type="button"
            onClick={() => void handleLogout()}
            className="btn-ghost rounded-[var(--radius-sm)] px-4 py-2.5 text-sm font-semibold"
          >
            Logout
          </button>
        </div>

        <button
          type="button"
          onClick={() => setMobileOpen(true)}
          className="flex h-9 w-9 items-center justify-center rounded-[var(--radius-sm)] text-fg-muted transition hover:bg-surface-hover hover:text-fg md:hidden"
          aria-label="Open menu"
        >
          <MenuIcon />
        </button>
      </div>

      {mobileOpen && (
        <div className="fixed inset-0 z-50 md:hidden" role="dialog" aria-modal="true">
          <button
            type="button"
            className="absolute inset-0 bg-black/60 backdrop-blur-sm"
            onClick={() => setMobileOpen(false)}
            aria-label="Close menu overlay"
          />

          <nav className="absolute right-0 top-0 flex h-full w-72 flex-col gap-1 border-l border-border bg-surface p-5 shadow-card-lg animate-slide-in">
            <div className="mb-4 flex items-center justify-between">
              <span className="flex items-center gap-2">
                <span className="inline-block h-2.5 w-2.5 rounded-full bg-accent" />
                <span className="text-sm font-bold text-fg">Guard Proxy</span>
              </span>
              <button
                type="button"
                onClick={() => setMobileOpen(false)}
                className="flex h-8 w-8 items-center justify-center rounded-[var(--radius-sm)] text-fg-muted transition hover:bg-surface-hover hover:text-fg"
                aria-label="Close menu"
              >
                <CloseIcon />
              </button>
            </div>

            {navigation.map((item) => (
              <NavLink
                key={item.to}
                to={item.to}
                onClick={() => setMobileOpen(false)}
                className={({ isActive }) => navLinkClass(isActive)}
              >
                {item.label}
              </NavLink>
            ))}

            <div className="my-3 h-px bg-border" />

            <button
              type="button"
              onClick={toggleTheme}
              className="flex items-center gap-2 rounded-[var(--radius-md)] px-4 py-2 text-sm font-medium text-fg-muted transition hover:bg-surface-hover hover:text-fg"
            >
              {theme === "emerald" ? <LeafIcon /> : <SnowflakeIcon />}
              <span>Theme: {theme}</span>
            </button>

            <div className="my-3 h-px bg-border" />

            <div className="flex flex-wrap gap-2 px-1">
              <span className="badge-accent rounded-[var(--radius-full)] bg-accent-soft px-4 py-1.5 text-sm font-semibold text-accent">
                Dev Mode
              </span>
              <span className="rounded-[var(--radius-full)] bg-surface-hover px-4 py-1.5 text-sm font-semibold text-fg-muted">
                {user?.full_name || user?.email || "No user"}
              </span>
            </div>

            <button
              type="button"
              onClick={() => void handleLogout()}
              className="btn-ghost mt-auto rounded-[var(--radius-md)] px-5 py-2.5 text-base font-semibold"
            >
              Logout
            </button>
          </nav>
        </div>
      )}
    </header>
  );
}
