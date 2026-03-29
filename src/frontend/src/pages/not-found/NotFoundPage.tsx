import { Link } from "react-router-dom";

import { appRoutes } from "@/app/routes";
import { EmptyState } from "@/components/shared/EmptyState";
import { PageHeader } from "@/components/shared/PageHeader";
import { useAuth } from "@/hooks/use-auth";

export function NotFoundPage() {
  const { isAuthenticated } = useAuth();
  const destination = isAuthenticated ? appRoutes.dashboard : appRoutes.login;
  const label = isAuthenticated ? "Return to dashboard" : "Go to login";

  return (
    <main className="grid min-h-screen place-items-center bg-app px-6 py-10 text-fg">
      <section className="w-full max-w-3xl space-y-8">
        <PageHeader
          eyebrow="404"
          title="This page does not exist"
          description="The route could not be matched. Use the shared navigation to get back to a valid part of the app."
        />

        <EmptyState
          title="Unknown route"
          description="This catch-all page protects the app from blank screens when someone enters a wrong URL or follows an outdated link."
          action={
            <Link to={destination} className="btn-primary px-4 py-2.5 text-sm">
              {label}
            </Link>
          }
        />
      </section>
    </main>
  );
}
