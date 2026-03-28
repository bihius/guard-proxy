import { PagePlaceholder } from "@/components/shared/PagePlaceholder";

export function LoginPage() {
  return (
    <main className="grid min-h-screen place-items-center bg-app px-6 py-10 text-fg">
      <div className="w-full max-w-xl card-gradient shadow-card-lg rounded-[var(--radius-xl)] border border-border p-8 backdrop-blur">
        <PagePlaceholder
          eyebrow="Auth"
          title="Login page placeholder"
          description="This route is intentionally simple for now. Replace with the real login form, token flow, and auth integration when ready."
        />
      </div>
    </main>
  );
}
