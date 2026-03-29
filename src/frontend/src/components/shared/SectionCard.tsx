import type { ReactNode } from "react";

type SectionCardProps = {
  title: string;
  description?: string;
  icon?: ReactNode;
  actions?: ReactNode;
  children: ReactNode;
};

export function SectionCard({
  title,
  description,
  icon,
  actions,
  children,
}: SectionCardProps) {
  return (
    <section className="card-gradient shadow-card rounded-[var(--radius-lg)] border border-border p-6">
      <div className="flex flex-col gap-4 border-b border-border-subtle pb-4 sm:flex-row sm:items-start sm:justify-between">
        <div className="flex items-start gap-3">
          {icon ? (
            <div className="flex h-10 w-10 items-center justify-center rounded-[var(--radius-md)] bg-accent-soft text-accent">
              {icon}
            </div>
          ) : null}

          <div className="space-y-1">
            <h2 className="text-lg font-semibold text-fg">{title}</h2>
            {description ? (
              <p className="text-sm leading-6 text-fg-muted">{description}</p>
            ) : null}
          </div>
        </div>

        {actions ? <div className="flex items-center gap-2">{actions}</div> : null}
      </div>

      <div className="pt-5">{children}</div>
    </section>
  );
}
