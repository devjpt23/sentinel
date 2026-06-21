import { cn, formatPct } from "@/lib/utils";
import { ArrowUpRight, ArrowDownRight, Minus } from "lucide-react";
import type { LucideIcon } from "lucide-react";

interface MetricCardProps {
  label: string;
  value: string;
  change?: number;
  icon?: LucideIcon;
  className?: string;
}

export function MetricCard({ label, value, change, icon: Icon, className }: MetricCardProps) {
  return (
    <div className={cn("rounded-xl border border-[#1e2d3a] bg-[#111922] p-4", className)}>
      <div className="flex items-center gap-2 mb-2">
        {Icon && <Icon className="h-4 w-4 text-[#6b7f8e]" />}
        <span className="text-xs text-[#6b7f8e]">{label}</span>
      </div>
      <p className="text-2xl font-bold text-[#f0f4f0]">{value}</p>
      {change !== undefined && (
        <div className={cn(
          "flex items-center gap-1 text-xs mt-1",
          change > 0 ? "text-[#84cc16]" : change < 0 ? "text-red-400" : "text-[#6b7f8e]"
        )}>
          {change > 0 ? (
            <ArrowUpRight className="h-3 w-3" />
          ) : change < 0 ? (
            <ArrowDownRight className="h-3 w-3" />
          ) : (
            <Minus className="h-3 w-3" />
          )}
          {formatPct(change)}
        </div>
      )}
    </div>
  );
}
