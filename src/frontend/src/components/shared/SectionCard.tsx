import type { ReactNode } from "react";

import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";

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
    <Card as="section">
      <CardHeader className="border-b border-border sm:flex-row sm:items-start sm:justify-between">
        <div className="flex items-start gap-3">
          {icon ? (
            <div className="flex h-9 w-9 items-center justify-center rounded-md bg-primary/10 text-primary">
              {icon}
            </div>
          ) : null}

          <div className="space-y-1">
            <CardTitle>{title}</CardTitle>
            {description ? (
              <CardDescription>{description}</CardDescription>
            ) : null}
          </div>
        </div>

        {actions ? <div className="flex items-center gap-2">{actions}</div> : null}
      </CardHeader>

      <CardContent className="pt-5">{children}</CardContent>
    </Card>
  );
}
