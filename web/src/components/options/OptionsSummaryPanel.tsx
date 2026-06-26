"use client";

import { Card } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { formatPrice, formatPercent } from "@/lib/utils";

interface OptionsSummaryPanelProps {
  summary: {
    atm_iv: number | null;
    put_call_ratio_oi: number | null;
    put_call_ratio_vol: number | null;
    max_pain: number | null;
    total_call_oi: number | null;
    total_put_oi: number | null;
  } | null;
  underlyingPrice: number | null;
  isLoading: boolean;
}

function getPcrColor(value: number | null): string {
  if (value === null) return "text-[#c8d8e4]";
  if (value < 0.7) return "text-emerald-400";
  if (value <= 1.0) return "text-yellow-400";
  return "text-red-400";
}

export function OptionsSummaryPanel({ summary, underlyingPrice, isLoading }: OptionsSummaryPanelProps) {
  if (isLoading) {
    return (
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        {Array.from({ length: 4 }).map((_, i) => (
          <Card key={i} className="p-4 bg-[#15202b] border-[#1e2d3a]">
            <Skeleton className="h-4 w-16 mb-2" />
            <Skeleton className="h-8 w-24" />
          </Card>
        ))}
      </div>
    );
  }

  return (
    <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
      {/* ATM IV */}
      <Card className="p-4 bg-[#15202b] border-[#1e2d3a]">
        <p className="text-xs text-[#6b7f8e] font-medium mb-1">ATM IV</p>
        <p className="text-2xl font-bold text-[#c8d8e4]">
          {summary?.atm_iv != null ? formatPercent(summary.atm_iv, 1) : "—"}
        </p>
      </Card>

      {/* PCR (OI) */}
      <Card className="p-4 bg-[#15202b] border-[#1e2d3a]">
        <p className="text-xs text-[#6b7f8e] font-medium mb-1">PCR (OI)</p>
        <p className={`text-2xl font-bold ${getPcrColor(summary?.put_call_ratio_oi ?? null)}`}>
          {summary?.put_call_ratio_oi != null ? summary.put_call_ratio_oi.toFixed(2) : "—"}
        </p>
      </Card>

      {/* PCR (Vol) */}
      <Card className="p-4 bg-[#15202b] border-[#1e2d3a]">
        <p className="text-xs text-[#6b7f8e] font-medium mb-1">PCR (Vol)</p>
        <p className={`text-2xl font-bold ${getPcrColor(summary?.put_call_ratio_vol ?? null)}`}>
          {summary?.put_call_ratio_vol != null ? summary.put_call_ratio_vol.toFixed(2) : "—"}
        </p>
      </Card>

      {/* Max Pain */}
      <Card className="p-4 bg-[#15202b] border-[#1e2d3a]">
        <p className="text-xs text-[#6b7f8e] font-medium mb-1">Max Pain</p>
        <p className="text-2xl font-bold text-[#c8d8e4]">
          {summary?.max_pain != null ? formatPrice(summary.max_pain) : "—"}
        </p>
      </Card>
    </div>
  );
}
