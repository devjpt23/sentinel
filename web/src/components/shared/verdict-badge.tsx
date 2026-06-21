import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";
import { getVerdictInfo } from "@/lib/utils";

interface VerdictBadgeProps {
  verdict: string;
  className?: string;
}

export function VerdictBadge({ verdict, className }: VerdictBadgeProps) {
  const { color, bg } = getVerdictInfo(verdict);

  return (
    <Badge
      variant="outline"
      className={cn("font-semibold", bg, className)}
    >
      <span className={color}>{verdict}</span>
    </Badge>
  );
}
