import { PagePlaceholder } from "@/components/shared/PagePlaceholder";

export function ForbiddenPage() {
  return (
    <PagePlaceholder
      eyebrow="Access denied"
      title="You do not have permission to view this area"
      description="This route is the shared fallback for role-based navigation guards. It lets us block admin-only screens without crashing the app or bouncing the user back to login."
    />
  );
}
