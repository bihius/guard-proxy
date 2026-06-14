import { CircleHelp } from "lucide-react";

type InfoTooltipProps = {
  label: string;
};

export function InfoTooltip({ label }: InfoTooltipProps) {
  return (
    <span className="group relative inline-flex">
      <button
        type="button"
        className="inline-flex h-5 w-5 items-center justify-center rounded-full text-muted-foreground transition hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background"
        aria-label={label}
        title={label}
      >
        <CircleHelp className="h-4 w-4" aria-hidden="true" />
      </button>
      <span className="pointer-events-none absolute left-1/2 top-6 z-50 hidden w-64 -translate-x-1/2 rounded-md border border-border bg-card px-3 py-2 text-xs font-normal leading-5 text-foreground shadow-lg group-hover:block group-focus-within:block">
        {label}
      </span>
    </span>
  );
}
