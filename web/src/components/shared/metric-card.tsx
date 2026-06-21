import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { cn, formatCurrency, formatPercent, formatPct } from "@/lib/utils";
import { ArrowUpRight, ArrowDownRight } from "lucide-react";

interface MetricCardProps {
  title: string;
  value: string | number;
  change?: number;
  prefix?: string;
  suffix?: string;
  description?: string;
  className?: string;
}

export function MetricCard({
  title,
  value,
  change,
  prefix = "",
  suffix = "",
  description,
  className,
}: MetricCardProps) {
  const displayValue = typeof value === "number" ? formatCurrency(value) : value;

  return (
    <Card className={className}>
      <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
        <CardTitle className="text-sm font-medium text-[#6b7f8e]">
          {title}
        </CardTitle>
      </CardHeader>
      <CardContent>
        <div className="text-2xl font-bold">
          {prefix}{displayValue}{suffix}
        </div>
        {change !== undefined && (
          <div className={cn(
            "flex items-center text-sm mt-1",
            change >= 0 ? "text-emerald-400" : "text-red-400"
          )}>
            {change >= 0 ? (
              <ArrowUpRight className="h-4 w-4 mr-1" />
            ) : (
              <ArrowDownRight className="h-4 w-4 mr-1" />
            )}
            {formatPct(change)}
          </div>
        )}
        {description && (
          <p className="text-xs text-[#6b7f8e] mt-1">{description}</p>
        )}
      </CardContent>
    </Card>
  );
}
