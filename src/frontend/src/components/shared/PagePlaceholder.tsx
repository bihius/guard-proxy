type PagePlaceholderProps = {
  title: string;
  description: string;
  eyebrow: string;
};

export function PagePlaceholder({
  title,
  description,
  eyebrow,
}: PagePlaceholderProps) {
  return (
    <section className="space-y-8">
      <header className="space-y-3">
        <span className="inline-block rounded-[var(--radius-full)] bg-accent-soft px-3 py-1 text-xs font-semibold tracking-wide text-accent">
          {eyebrow}
        </span>
        <h1 className="text-3xl font-bold tracking-tight text-fg sm:text-4xl">
          {title}
        </h1>
        <p className="max-w-3xl text-base leading-7 text-fg-muted">
          {description}
        </p>
      </header>

      <div className="grid gap-5 xl:grid-cols-[1.4fr_1fr]">
        <div className="card-gradient shadow-card rounded-[var(--radius-lg)] border border-border p-6">
          <h2 className="text-lg font-semibold text-fg">
            Why it exists
          </h2>
          <p className="mt-3 text-sm leading-6 text-fg-muted">
            This is a shared placeholder so every route already lives inside the
            same application shell. Team members can now replace only the inside
            of the page without rebuilding layout, navigation, or page chrome.
          </p>
        </div>

        <div className="shadow-card rounded-[var(--radius-lg)] border border-border bg-surface p-6">
          <h2 className="text-lg font-semibold text-fg">
            Next step
          </h2>
          <p className="mt-3 text-sm leading-6 text-fg-muted">
            Replace this block with the real feature when the assigned frontend
            task starts.
          </p>
        </div>
      </div>
    </section>
  );
}
