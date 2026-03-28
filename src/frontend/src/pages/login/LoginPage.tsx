import { type FormEvent, useState } from "react";
import { useNavigate } from "react-router-dom";

export function LoginPage() {
  const navigate = useNavigate();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setLoading(true);

    // TODO: replace with real auth call
    setTimeout(() => {
      setLoading(false);
      if (email && password.length >= 12) {
        navigate("/dashboard");
      } else {
        setError(
          password.length < 12
            ? "Password must be at least 12 characters."
            : "Please enter a valid email.",
        );
      }
    }, 600);
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
          {error && (
            <div className="rounded-[var(--radius-md)] bg-error-soft px-4 py-3 text-sm font-medium text-error">
              {error}
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
              placeholder="admin@example.com"
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
              placeholder="Min. 12 characters"
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

function ShieldIcon() {
  return (
    <svg
      width="20"
      height="20"
      viewBox="0 0 20 20"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.6"
      strokeLinecap="round"
      strokeLinejoin="round"
      className="text-accent-fg"
    >
      <path d="M10 2 L3 6 L3 11 C3 15 6 18 10 19 C14 18 17 15 17 11 L17 6 Z" />
      <polyline points="7 10 9.5 12.5 13.5 7.5" />
    </svg>
  );
}
