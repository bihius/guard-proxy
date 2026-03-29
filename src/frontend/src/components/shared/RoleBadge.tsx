import type { UserRole } from "@/types/api";

import { StatusBadge } from "./StatusBadge";

type RoleBadgeProps = {
  role: UserRole;
};

export function RoleBadge({ role }: RoleBadgeProps) {
  return (
    <StatusBadge
      label={role === "admin" ? "Admin" : "Viewer"}
      tone={role === "admin" ? "info" : "neutral"}
    />
  );
}
