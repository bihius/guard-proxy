type LoadingStateProps = {
  label?: string;
};

export function LoadingState({
  label = "Loading content...",
}: LoadingStateProps) {
  return (
    <div className="rounded-[var(--radius-lg)] border border-border bg-surface p-6">
      <div className="flex items-center gap-3">
        <span className="h-4 w-4 animate-spin rounded-full border-2 border-border border-t-accent" />
        <p className="text-sm font-medium text-fg-muted">{label}</p>
      </div>
    </div>
  );
}
