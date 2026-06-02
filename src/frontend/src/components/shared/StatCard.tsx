import type { ReactNode } from "react";

import { Card } from "@/components/ui/card";
import { cn } from "@/lib/utils";

type StatCardProps = {
  label: string;
  value: string;
  hint?: string;
  tone?: "neutral" | "success" | "warning" | "error" | "info";
  icon?: ReactNode;
  isLoading?: boolean;
};

const toneClassMap = {
  neutral: "bg-muted text-muted-foreground",
  success: "bg-success/10 text-success",
  warning: "bg-warning/10 text-warning",
  error: "bg-destructive/10 text-destructive",
  info: "bg-info/10 text-info",
} as const;

export function StatCard({
  label,
  value,
  hint,
  tone = "neutral",
  icon,
  isLoading = false,
}: StatCardProps) {
  return (
    <Card as="article" className="p-5">
      <div className="flex items-start justify-between gap-3">
        <div className="space-y-2">
          <p className="text-sm font-medium text-muted-foreground">{label}</p>
          {isLoading ? (
            <div
              className="h-9 w-16 animate-pulse rounded-md bg-muted"
              role="status"
              aria-label="Loading"
            />
          ) : (
            <p className="font-mono text-3xl font-semibold tracking-normal text-foreground">
              {value}
            </p>
          )}
        </div>

        {icon ? (
          <div
            className={cn(
              "flex h-9 w-9 items-center justify-center rounded-md",
              toneClassMap[tone],
            )}
          >
            {icon}
          </div>
        ) : null}
      </div>

      {hint ? <p className="mt-4 text-sm leading-6 text-muted-foreground">{hint}</p> : null}
    </Card>
  );
}
