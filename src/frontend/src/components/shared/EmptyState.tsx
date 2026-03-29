import type { ReactNode } from "react";

type EmptyStateProps = {
  title: string;
  description: string;
  action?: ReactNode;
};

export function EmptyState({
  title,
  description,
  action,
}: EmptyStateProps) {
  return (
    <div className="rounded-[var(--radius-lg)] border border-dashed border-border bg-surface p-8 text-center">
      <div className="mx-auto max-w-xl space-y-3">
        <h3 className="text-lg font-semibold text-fg">{title}</h3>
        <p className="text-sm leading-6 text-fg-muted">{description}</p>
        {action ? <div className="pt-2">{action}</div> : null}
      </div>
    </div>
  );
}
