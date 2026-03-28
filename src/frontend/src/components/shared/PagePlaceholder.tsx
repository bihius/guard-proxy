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
    <section className="space-y-6">
      <header className="space-y-3">
        <p className="text-xs font-bold uppercase tracking-[0.2em] text-cyan-400">
          {eyebrow}
        </p>
        <h1 className="text-3xl font-semibold tracking-tight text-slate-50 sm:text-4xl">
          {title}
        </h1>
        <p className="max-w-3xl text-base leading-7 text-slate-400">
          {description}
        </p>
      </header>

      <div className="grid gap-4 xl:grid-cols-[1.4fr_1fr]">
        <div className="rounded-3xl border border-slate-800 bg-slate-900/80 p-6">
          <h2 className="text-lg font-semibold text-slate-100">Why it exists</h2>
          <p className="mt-3 text-sm leading-6 text-slate-400">
            This is a shared placeholder so every route already lives inside the
            same application shell. Team members can now replace only the inside
            of the page without rebuilding layout, navigation, or page chrome.
          </p>
        </div>

        <div className="rounded-3xl border border-slate-800 bg-slate-900/50 p-6">
          <h2 className="text-lg font-semibold text-slate-100">Next step</h2>
          <p className="mt-3 text-sm leading-6 text-slate-400">
            Replace this block with the real feature when the assigned frontend
            task starts.
          </p>
        </div>
      </div>
    </section>
  );
}
