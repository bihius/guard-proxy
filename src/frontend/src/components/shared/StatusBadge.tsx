import { Badge } from "@/components/ui/badge";

type StatusBadgeTone = "success" | "warning" | "error" | "info" | "neutral";

type StatusBadgeProps = {
  label: string;
  tone?: StatusBadgeTone;
};

const toneVariantMap = {
  success: "success",
  warning: "warning",
  error: "destructive",
  info: "default",
  neutral: "outline",
} as const;

export function StatusBadge({
  label,
  tone = "neutral",
}: StatusBadgeProps) {
  return (
    <Badge variant={toneVariantMap[tone]}>
      <span className="h-1.5 w-1.5 rounded-full bg-current" />
      {label}
    </Badge>
  );
}
