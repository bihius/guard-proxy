import { useCallback, useEffect, useState } from "react";
import { NavLink, Link } from "react-router-dom";

const navigation = [
  { to: "/dashboard", label: "Dashboard" },
  { to: "/vhosts", label: "VHosts" },
  { to: "/policies", label: "Policies" },
];

const THEMES = ["emerald", "frost"] as const;
type Theme = (typeof THEMES)[number];
const STORAGE_KEY = "guard-proxy-theme";

function getStoredTheme(): Theme {
  try {
    const stored = localStorage.getItem(STORAGE_KEY);
    if (stored && THEMES.includes(stored as Theme)) return stored as Theme;
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
    localStorage.setItem(STORAGE_KEY, theme);
  } catch {
    /* privacy mode */
  }
}

export function NavBar() {
  const [mobileOpen, setMobileOpen] = useState(false);
  const [theme, setTheme] = useState<Theme>(getStoredTheme);

  useEffect(() => {
    applyTheme(theme);
  }, [theme]);

  useEffect(() => {
    if (!mobileOpen) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setMobileOpen(false);
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [mobileOpen]);

  const toggleTheme = useCallback(() => {
    setTheme((t) => (t === "emerald" ? "frost" : "emerald"));
  }, []);

  const navLinkClass = (isActive: boolean, pill = false) =>
    [
      pill
        ? "rounded-[var(--radius-full)] px-3 py-2"
        : "rounded-[var(--radius-md)] px-4 py-2",
      "text-sm font-medium transition-all duration-150",
      isActive
        ? "bg-accent-soft text-accent"
        : "text-fg-muted hover:bg-surface-hover hover:text-fg",
    ].join(" ");

  return (
    <header className="nav-surface sticky top-0 z-50 h-14 border-b border-border backdrop-blur-xl">
      <div className="flex h-full items-center justify-between px-6 lg:px-10">
        <Link
          to="/dashboard"
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
            onClick={toggleTheme}
            className="flex h-8 w-8 items-center justify-center rounded-[var(--radius-sm)] text-fg-muted transition hover:bg-surface-hover hover:text-fg"
            aria-label={`Switch to ${theme === "emerald" ? "frost" : "emerald"} theme`}
            title={`Theme: ${theme}`}
          >
            {theme === "emerald" ? <LeafIcon /> : <SnowflakeIcon />}
          </button>

          <span className="rounded-[var(--radius-full)] bg-accent-soft px-3 py-1 text-xs font-semibold text-accent">
            Dev Mode
          </span>
          <span className="rounded-[var(--radius-full)] bg-surface-hover px-3 py-1 text-xs font-semibold text-fg-muted">
            Role: Unknown
          </span>
          <Link
            to="/login"
            className="btn-ghost rounded-[var(--radius-sm)] px-3 py-2 text-xs font-semibold"
          >
            Logout
          </Link>
        </div>

        <button
          onClick={() => setMobileOpen(true)}
          className="flex h-9 w-9 items-center justify-center rounded-[var(--radius-sm)] text-fg-muted transition hover:bg-surface-hover hover:text-fg md:hidden"
          aria-label="Open menu"
        >
          <svg
            width="20"
            height="20"
            viewBox="0 0 20 20"
            fill="none"
            stroke="currentColor"
            strokeWidth="1.8"
            strokeLinecap="round"
          >
            <line x1="3" y1="5" x2="17" y2="5" />
            <line x1="3" y1="10" x2="17" y2="10" />
            <line x1="3" y1="15" x2="17" y2="15" />
          </svg>
        </button>
      </div>

      {mobileOpen && (
        <div className="fixed inset-0 z-50 md:hidden" role="dialog" aria-modal="true">
          <div
            className="absolute inset-0 bg-black/60 backdrop-blur-sm"
            onClick={() => setMobileOpen(false)}
          />
          <nav className="absolute right-0 top-0 flex h-full w-72 flex-col gap-1 border-l border-border bg-surface p-5 shadow-card-lg animate-slide-in">
            <div className="mb-4 flex items-center justify-between">
              <span className="flex items-center gap-2">
                <span className="inline-block h-2.5 w-2.5 rounded-full bg-accent" />
                <span className="text-sm font-bold text-fg">Guard Proxy</span>
              </span>
              <button
                onClick={() => setMobileOpen(false)}
                className="flex h-8 w-8 items-center justify-center rounded-[var(--radius-sm)] text-fg-muted transition hover:bg-surface-hover hover:text-fg"
                aria-label="Close menu"
              >
                <svg
                  width="18"
                  height="18"
                  viewBox="0 0 18 18"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="1.8"
                  strokeLinecap="round"
                >
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
                className={({ isActive }) => navLinkClass(isActive)}
              >
                {item.label}
              </NavLink>
            ))}

            <div className="my-3 h-px bg-border" />

            <button
              onClick={toggleTheme}
              className="flex items-center gap-2 rounded-[var(--radius-md)] px-4 py-2 text-sm font-medium text-fg-muted transition hover:bg-surface-hover hover:text-fg"
            >
              {theme === "emerald" ? <LeafIcon /> : <SnowflakeIcon />}
              <span>Theme: {theme}</span>
            </button>

            <div className="my-3 h-px bg-border" />

            <div className="flex flex-wrap gap-2 px-1">
              <span className="rounded-[var(--radius-full)] bg-accent-soft px-3 py-1 text-xs font-semibold text-accent">
                Dev Mode
              </span>
              <span className="rounded-[var(--radius-full)] bg-surface-hover px-3 py-1 text-xs font-semibold text-fg-muted">
                Role: Unknown
              </span>
            </div>

            <Link
              to="/login"
              onClick={() => setMobileOpen(false)}
              className="btn-ghost mt-auto rounded-[var(--radius-md)] px-4 py-2 text-sm font-semibold"
            >
              Logout
            </Link>
          </nav>
        </div>
      )}
    </header>
  );
}

function LeafIcon() {
  return (
    <svg
      width="16"
      height="16"
      viewBox="0 0 16 16"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.4"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <path d="M4 14s1-6 8-10c-4 4-6 7-8 10z" />
      <path d="M4 14c2-2 4-3 8-4" />
    </svg>
  );
}

function SnowflakeIcon() {
  return (
    <svg
      width="16"
      height="16"
      viewBox="0 0 16 16"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.4"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <line x1="8" y1="1" x2="8" y2="15" />
      <line x1="1" y1="8" x2="15" y2="8" />
      <line x1="3" y1="3" x2="13" y2="13" />
      <line x1="13" y1="3" x2="3" y2="13" />
      <line x1="8" y1="1" x2="6.5" y2="3" />
      <line x1="8" y1="1" x2="9.5" y2="3" />
      <line x1="8" y1="15" x2="6.5" y2="13" />
      <line x1="8" y1="15" x2="9.5" y2="13" />
    </svg>
  );
}
