import { PagePlaceholder } from "@/components/shared/PagePlaceholder";

export function LoginPage() {
  return (
    <main className="grid min-h-screen place-items-center bg-app px-6 py-10 text-slate-100">
      <div className="w-full max-w-xl rounded-3xl border border-slate-800 bg-slate-900/85 p-8 shadow-[0_32px_80px_rgba(2,6,23,0.45)] backdrop-blur">
        <PagePlaceholder
          eyebrow="Auth"
          title="Login page placeholder"
          description="This route is intentionally simple for now. Kamyk can later replace the inside with the real login form, token flow, and auth integration."
        />
      </div>
    </main>
  );
}
