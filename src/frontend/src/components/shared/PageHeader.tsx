import type { ReactNode } from "react";

type PageHeaderProps = {
  eyebrow?: string;
  title: string;
  description?: string;
  actions?: ReactNode;
};

export function PageHeader({
  eyebrow,
  title,
  description,
  actions,
}: PageHeaderProps) {
  return (
    <header className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
      <div className="space-y-3">
        {eyebrow ? (
          <span className="inline-block rounded-[var(--radius-full)] bg-accent-soft px-3 py-1 text-xs font-semibold uppercase tracking-wide text-accent">
            {eyebrow}
          </span>
        ) : null}

        <div className="space-y-2">
          <h1 className="text-3xl font-bold tracking-tight text-fg sm:text-4xl">
            {title}
          </h1>
          {description ? (
            <p className="max-w-3xl text-base leading-7 text-fg-muted">
              {description}
            </p>
          ) : null}
        </div>
      </div>

      {actions ? (
        <div className="flex flex-wrap items-center gap-3">{actions}</div>
      ) : null}
    </header>
  );
}
