import { type FormEvent, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";

import { appRoutes } from "@/app/routes";
import { ShieldIcon } from "@/components/icons";
import { useAuth } from "@/hooks/use-auth";

export function LoginPage() {
  const navigate = useNavigate();
  const location = useLocation();
  const { loginError, signIn } = useAuth();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setLoading(true);

    try {
      await signIn({
        email,
        password,
      });

      const from = location.state as { from?: { pathname?: string } } | null;
      navigate(from?.from?.pathname ?? appRoutes.dashboard, {
        replace: true,
      });
    } catch {
      // AuthContext exposes the user-facing login error.
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="grid min-h-screen place-items-center bg-app px-6 py-10 text-fg">
      <div className="w-full max-w-md">
        <div className="mb-8 text-center">
          <div className="mx-auto mb-4 flex h-10 w-10 items-center justify-center rounded-full bg-accent">
            <ShieldIcon />
          </div>
          <h1 className="text-2xl font-bold tracking-tight text-fg">
            Guard Proxy
          </h1>
          <p className="mt-2 text-sm text-fg-muted">
            Sign in to the admin panel
          </p>
        </div>

        <form
          onSubmit={handleSubmit}
          className="card-gradient shadow-card-lg rounded-[var(--radius-xl)] border border-border p-8 space-y-5"
        >
          {loginError && (
            <div
              role="alert"
              aria-live="assertive"
              className="rounded-[var(--radius-md)] bg-error-soft px-4 py-3 text-sm font-medium text-error"
            >
              {loginError}
            </div>
          )}

          <div className="space-y-1.5">
            <label htmlFor="email" className="block text-sm font-medium text-fg-muted">
              Email
            </label>
            <input
              id="email"
              type="email"
              autoComplete="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className="input-field"
            />
          </div>

          <div className="space-y-1.5">
            <label htmlFor="password" className="block text-sm font-medium text-fg-muted">
              Password
            </label>
            <input
              id="password"
              type="password"
              autoComplete="current-password"
              required
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="input-field"
            />
          </div>

          <button
            type="submit"
            disabled={loading}
            className="btn-primary w-full px-4 py-2.5 text-sm"
          >
            {loading ? "Signing in\u2026" : "Sign in"}
          </button>
        </form>

        <p className="mt-6 text-center text-xs text-fg-subtle">
          Protected by Guard Proxy WAF
        </p>
      </div>
    </main>
  );
}
