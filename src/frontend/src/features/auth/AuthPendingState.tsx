import { Card } from "@/components/ui/card";

export function AuthPendingState() {
  return (
    <main className="grid min-h-screen place-items-center bg-app px-6 py-10 text-foreground">
      <Card className="px-6 py-5 text-sm text-muted-foreground">
        Checking session...
      </Card>
    </main>
  );
}
