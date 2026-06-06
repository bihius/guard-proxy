import { type FormEvent, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { Shield } from "lucide-react";

import { appRoutes } from "@/app/routes";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
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
    <main className="grid min-h-screen place-items-center bg-app px-6 py-10 text-foreground">
      <div className="w-full max-w-md">
        <div className="mb-8 text-center">
          <div className="mx-auto mb-4 flex h-11 w-11 items-center justify-center rounded-lg border border-border bg-card text-primary shadow-sm">
            <Shield className="h-5 w-5" />
          </div>
          <h1 className="text-2xl font-semibold tracking-normal text-foreground">
            Guard Proxy
          </h1>
          <p className="mt-2 text-sm text-muted-foreground">
            Sign in to the admin panel
          </p>
        </div>

        <Card>
          <CardHeader>
            <CardTitle>Admin access</CardTitle>
          </CardHeader>
          <CardContent>
            <form onSubmit={handleSubmit} className="space-y-5">
              {loginError && (
                <Alert variant="destructive" aria-live="assertive">
                  {loginError}
                </Alert>
              )}

              <div className="space-y-1.5">
                <Label htmlFor="email">Email</Label>
                <Input
                  id="email"
                  type="email"
                  autoComplete="email"
                  required
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                />
              </div>

              <div className="space-y-1.5">
                <Label htmlFor="password">Password</Label>
                <Input
                  id="password"
                  type="password"
                  autoComplete="current-password"
                  required
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                />
              </div>

              <Button type="submit" disabled={loading} className="w-full">
                {loading ? "Signing in\u2026" : "Sign in"}
              </Button>
            </form>
          </CardContent>
        </Card>

        <p className="mt-6 text-center text-xs text-muted-foreground">
          Protected by Guard Proxy WAF
        </p>
      </div>
    </main>
  );
}
