import type { ReactNode } from "react";

type ErrorStateProps = {
  title: string;
  description: string;
  action?: ReactNode;
};

export function ErrorState({
  title,
  description,
  action,
}: ErrorStateProps) {
  return (
    <div className="rounded-[var(--radius-lg)] border border-error/30 bg-error-soft p-6">
      <div className="space-y-2">
        <h3 className="text-lg font-semibold text-error">{title}</h3>
        <p className="text-sm leading-6 text-fg">{description}</p>
        {action ? <div className="pt-2">{action}</div> : null}
      </div>
    </div>
  );
}
