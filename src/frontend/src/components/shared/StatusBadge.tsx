type StatusBadgeTone = "success" | "warning" | "error" | "info" | "neutral";

type StatusBadgeProps = {
  label: string;
  tone?: StatusBadgeTone;
};

const toneClassMap = {
  success: "bg-success-soft text-success",
  warning: "bg-warning-soft text-warning",
  error: "bg-error-soft text-error",
  info: "bg-info-soft text-info",
  neutral: "bg-surface-hover text-fg-muted",
} as const;

export function StatusBadge({
  label,
  tone = "neutral",
}: StatusBadgeProps) {
  return (
    <span
      className={`inline-flex items-center gap-2 rounded-[var(--radius-full)] px-3 py-1 text-xs font-semibold ${toneClassMap[tone]}`}
    >
      <span className="h-1.5 w-1.5 rounded-full bg-current" />
      {label}
    </span>
  );
}
