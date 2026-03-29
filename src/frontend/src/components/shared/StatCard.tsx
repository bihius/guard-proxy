import type { ReactNode } from "react";

type StatCardProps = {
  label: string;
  value: string;
  hint?: string;
  tone?: "neutral" | "success" | "warning" | "error" | "info";
  icon?: ReactNode;
};

const toneClassMap = {
  neutral: "bg-surface-hover text-fg-muted",
  success: "bg-success-soft text-success",
  warning: "bg-warning-soft text-warning",
  error: "bg-error-soft text-error",
  info: "bg-info-soft text-info",
} as const;

export function StatCard({
  label,
  value,
  hint,
  tone = "neutral",
  icon,
}: StatCardProps) {
  return (
    <article className="shadow-card rounded-[var(--radius-lg)] border border-border bg-surface p-5">
      <div className="flex items-start justify-between gap-3">
        <div className="space-y-2">
          <p className="text-sm font-medium text-fg-muted">{label}</p>
          <p className="font-mono text-3xl font-semibold tracking-tight text-fg">
            {value}
          </p>
        </div>

        {icon ? (
          <div
            className={`flex h-10 w-10 items-center justify-center rounded-[var(--radius-md)] ${toneClassMap[tone]}`}
          >
            {icon}
          </div>
        ) : null}
      </div>

      {hint ? <p className="mt-4 text-sm leading-6 text-fg-muted">{hint}</p> : null}
    </article>
  );
}
