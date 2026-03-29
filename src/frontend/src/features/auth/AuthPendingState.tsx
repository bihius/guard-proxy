export function AuthPendingState() {
  return (
    <main className="grid min-h-screen place-items-center bg-app px-6 py-10 text-fg">
      <div className="card-gradient shadow-card rounded-[var(--radius-lg)] border border-border px-6 py-5 text-sm text-fg-muted">
        Checking session...
      </div>
    </main>
  );
}
