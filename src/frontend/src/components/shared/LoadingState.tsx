import { Card } from "@/components/ui/card";

type LoadingStateProps = {
  label?: string;
};

export function LoadingState({
  label = "Loading content...",
}: LoadingStateProps) {
  return (
    <Card className="p-5">
      <div className="flex items-center gap-3">
        <span className="h-4 w-4 animate-spin rounded-full border-2 border-border border-t-primary" />
        <p className="text-sm font-medium text-muted-foreground">{label}</p>
      </div>
    </Card>
  );
}
