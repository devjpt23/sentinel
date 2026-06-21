import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";

interface ScoreCardProps {
  title: string;
  score: number;
  maxScore?: number;
  verdict?: string;
  description?: string;
  className?: string;
}

export function ScoreCard({
  title,
  score,
  maxScore = 100,
  verdict,
  description,
  className,
}: ScoreCardProps) {
  const percentage = (score / maxScore) * 100;
  const color =
    percentage >= 70
      ? "text-emerald-400"
      : percentage >= 40
        ? "text-yellow-400"
        : "text-red-400";

  const barColor =
    percentage >= 70
      ? "bg-emerald-500"
      : percentage >= 40
        ? "bg-yellow-500"
        : "bg-red-500";

  return (
    <Card className={cn("relative overflow-hidden", className)}>
      <CardHeader className="pb-2">
        <div className="flex items-center justify-between">
          <CardTitle className="text-sm font-medium text-[#6b7f8e]">
            {title}
          </CardTitle>
          {verdict && <Badge variant="outline">{verdict}</Badge>}
        </div>
      </CardHeader>
      <CardContent>
        <div className="flex items-end gap-4">
          <div>
            <span className={cn("text-3xl font-bold", color)}>
              {score}
            </span>
            <span className="text-sm text-[#6b7f8e] ml-1">
              /{maxScore}
            </span>
          </div>
          <div className="flex-1">
            <div className="h-2 w-full rounded-full bg-muted">
              <div
                className={cn("h-full rounded-full transition-all", barColor)}
                style={{ width: `${percentage}%` }}
              />
            </div>
          </div>
        </div>
        {description && (
          <p className="text-xs text-[#6b7f8e] mt-2">{description}</p>
        )}
      </CardContent>
    </Card>
  );
}
