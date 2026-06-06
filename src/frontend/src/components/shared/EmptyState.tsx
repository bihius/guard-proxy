import type { ReactNode } from "react";

import { Card } from "@/components/ui/card";

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
    <Card className="border-dashed p-8 text-center">
      <div className="mx-auto max-w-xl space-y-3">
        <h3 className="text-base font-semibold text-foreground">{title}</h3>
        <p className="text-sm leading-6 text-muted-foreground">{description}</p>
        {action ? <div className="pt-2">{action}</div> : null}
      </div>
    </Card>
  );
}
