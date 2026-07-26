import { Badge } from "@/components/ui/badge";

const tone: Record<string, "success" | "warning" | "danger" | "secondary" | "outline"> = {
  completed: "success",
  ready: "success",
  running: "outline",
  pending: "secondary",
  failed: "danger",
  error: "danger",
  skipped: "secondary",
  low: "success",
  medium: "warning",
  high: "danger",
  audit: "outline",
  feature: "secondary",
  bug_fix: "secondary",
};

export function StatusBadge({ value }: { value: string }) {
  return <Badge variant={tone[value] ?? "secondary"}>{value}</Badge>;
}
