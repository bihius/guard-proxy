import { useCallback, useEffect, useState } from "react";
import { Link, NavLink, useNavigate } from "react-router-dom";
import { Leaf, LogOut, Menu, Shield, Snowflake, X } from "lucide-react";

import { appRoutes } from "@/app/routes";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { ApplyConfigButton } from "@/features/runtime/ApplyConfigButton";
import { useApplyNotice } from "@/features/runtime/use-apply-notice";
import { useRuntimeStatus } from "@/features/runtime/use-runtime-status";
import { useAuth } from "@/hooks/use-auth";
import { THEMES, type Theme, getThemeStorageKey } from "@/lib/theme";
import { cn } from "@/lib/utils";

const navigation = [
  { to: appRoutes.dashboard, label: "Dashboard" },
  { to: appRoutes.vhosts, label: "VHosts" },
  { to: appRoutes.policies, label: "Policies" },
  { to: appRoutes.logs, label: "Logs" },
  { to: appRoutes.bannedIps, label: "Banned IPs" },
];

function navLinkClass(isActive: boolean, pill = false) {
  return cn(
    pill
      ? "rounded-[var(--radius-full)] px-3 py-2"
      : "rounded-[var(--radius-md)] px-4 py-2",
    "text-sm font-medium transition-all duration-150",
    isActive
      ? "nav-link-active bg-primary/10 text-primary"
      : "text-muted-foreground hover:bg-accent hover:text-accent-foreground",
  );
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
    meta.setAttribute("content", theme === "frost" ? "#f8f9fc" : "#1a2e1a");
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
  const runtimeStatus = useRuntimeStatus();
  const { showNotice } = useApplyNotice();
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
          <span className="flex h-8 w-8 items-center justify-center rounded-md border border-border bg-card text-primary">
            <Shield className="h-4 w-4" />
          </span>
          <span className="text-base font-semibold tracking-normal text-foreground">
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
          <ApplyConfigButton runtimeStatus={runtimeStatus} onResult={showNotice} />

          <Button
            type="button"
            onClick={toggleTheme}
            variant="ghost"
            size="icon"
            aria-label={`Switch to ${theme === "emerald" ? "frost" : "emerald"} theme`}
            title={`Theme: ${theme}`}
          >
            {theme === "emerald" ? <Leaf /> : <Snowflake />}
          </Button>

          <div className="mx-1 h-6 w-px bg-border" aria-hidden="true" />

          <span className="max-w-48 truncate text-sm text-muted-foreground">
            {user?.full_name || user?.email || "No user"}
          </span>
          <Button
            type="button"
            onClick={() => void handleLogout()}
            variant="ghost"
            size="icon"
            aria-label="Log out"
            title="Log out"
          >
            <LogOut />
          </Button>
        </div>

        <Button
          type="button"
          onClick={() => setMobileOpen(true)}
          variant="ghost"
          size="icon"
          className="md:hidden"
          aria-label="Open menu"
        >
          <Menu />
        </Button>
      </div>

      {mobileOpen && (
        <div className="fixed inset-0 z-50 md:hidden" role="dialog" aria-modal="true">
          <button
            type="button"
            className="absolute inset-0 bg-black/60 backdrop-blur-sm"
            onClick={() => setMobileOpen(false)}
            aria-label="Close menu overlay"
          />

          <nav className="fixed right-0 top-0 flex h-dvh w-72 max-w-[calc(100vw-2rem)] flex-col gap-1 border-l border-border bg-card p-5 shadow-lg animate-slide-in">
            <div className="mb-4 flex items-center justify-between">
              <span className="flex items-center gap-2">
                <span className="flex h-8 w-8 items-center justify-center rounded-md border border-border text-primary">
                  <Shield className="h-4 w-4" />
                </span>
                <span className="text-sm font-semibold text-foreground">Guard Proxy</span>
              </span>
              <Button
                type="button"
                onClick={() => setMobileOpen(false)}
                variant="ghost"
                size="icon"
                aria-label="Close menu"
              >
                <X />
              </Button>
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

            <ApplyConfigButton runtimeStatus={runtimeStatus} onResult={showNotice} />

            <Button
              type="button"
              onClick={toggleTheme}
              variant="ghost"
              className="justify-start"
            >
              {theme === "emerald" ? <Leaf /> : <Snowflake />}
              <span>Theme: {theme}</span>
            </Button>

            <div className="my-3 h-px bg-border" />

            <div className="flex flex-wrap gap-2 px-1">
              <Badge variant="secondary">
                {user?.full_name || user?.email || "No user"}
              </Badge>
            </div>

            <Button
              type="button"
              onClick={() => void handleLogout()}
              variant="outline"
              className="mt-auto"
            >
              <LogOut />
              Logout
            </Button>
          </nav>
        </div>
      )}
    </header>
  );
}
