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
        <span className="inline-block rounded-[var(--radius-full)] bg-accent-soft px-3 py-1 text-xs font-semibold tracking-wide uppercase text-accent">
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
          <div className="mb-3 flex h-8 w-8 items-center justify-center rounded-[var(--radius-sm)] bg-accent-soft">
            <InfoIcon />
          </div>
          <h2 className="text-lg font-semibold text-fg">
            Why it exists
          </h2>
          <p className="mt-2 text-sm leading-6 text-fg-muted">
            Shared placeholder so every route lives inside the same application
            shell. Replace only the page content without rebuilding layout,
            navigation, or chrome.
          </p>
        </div>

        <div className="shadow-card rounded-[var(--radius-lg)] border border-border bg-surface p-6">
          <div className="mb-3 flex h-8 w-8 items-center justify-center rounded-[var(--radius-sm)] bg-surface-hover">
            <ArrowIcon />
          </div>
          <h2 className="text-lg font-semibold text-fg">
            Next step
          </h2>
          <p className="mt-2 text-sm leading-6 text-fg-muted">
            Replace this block with the real feature when the assigned frontend
            task starts.
          </p>
        </div>
      </div>
    </section>
  );
}

function InfoIcon() {
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
      className="text-accent"
    >
      <circle cx="8" cy="8" r="6.5" />
      <line x1="8" y1="7" x2="8" y2="11" />
      <circle cx="8" cy="5" r="0.5" fill="currentColor" />
    </svg>
  );
}

function ArrowIcon() {
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
      className="text-fg-muted"
    >
      <line x1="3" y1="8" x2="13" y2="8" />
      <polyline points="9 4 13 8 9 12" />
    </svg>
  );
}
