import type { ReactNode } from "react";

import { Alert } from "@/components/ui/alert";

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
    <Alert variant="destructive" className="p-5">
      <div className="space-y-2">
        <h3 className="text-base font-semibold">{title}</h3>
        <p className="text-sm leading-6 text-foreground">{description}</p>
        {action ? <div className="pt-2">{action}</div> : null}
      </div>
    </Alert>
  );
}
