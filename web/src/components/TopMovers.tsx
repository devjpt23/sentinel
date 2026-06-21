"use client";

import { Card, CardContent } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { useMarketMovers } from "@/hooks/use-market-data";
import { formatPrice, formatPct } from "@/lib/utils";
import { ArrowUpRight, ArrowDownRight } from "lucide-react";

function MoverList({ movers, type }: { movers: { ticker: string; name: string; price: number; change_pct: number }[]; type: "gainer" | "loser" }) {
  if (!movers.length) {
    return <p className="text-xs text-[#6b7f8e] text-center py-8">No data available</p>;
  }
  return (
    <div className="space-y-1">
      {movers.map((m) => (
        <a
          key={m.ticker}
          href={`/company/${m.ticker}`}
          className="flex items-center justify-between w-full py-2 px-3 rounded-lg hover:bg-[#1a2a38]/50 transition-colors group"
        >
          <div className="flex items-center gap-3 min-w-0">
            <span className={`flex items-center gap-0.5 text-xs shrink-0 ${type === "gainer" ? "text-[#84cc16]" : "text-red-400"}`}>
              {type === "gainer" ? <ArrowUpRight className="h-3.5 w-3.5" /> : <ArrowDownRight className="h-3.5 w-3.5" />}
            </span>
            <div className="min-w-0">
              <p className="text-sm font-mono font-semibold text-[#f0f4f0]">{m.ticker}</p>
              <p className="text-[11px] text-[#6b7f8e] truncate">{m.name}</p>
            </div>
          </div>
          <div className="text-right shrink-0 ml-3">
            <p className="text-sm font-mono text-[#c8d8e4]">{formatPrice(m.price)}</p>
            <p className={`text-xs font-mono ${m.change_pct >= 0 ? "text-[#84cc16]" : "text-red-400"}`}>
              {formatPct(m.change_pct)}
            </p>
          </div>
        </a>
      ))}
    </div>
  );
}

export function TopMovers() {
  const { data, isLoading, error } = useMarketMovers();

  if (isLoading) {
    return (
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4 w-full max-w-3xl mx-auto">
        {[1, 2].map((i) => (
          <Card key={i} className="p-4">
            <Skeleton className="h-4 w-28 mb-4" />
            {Array.from({ length: 5 }).map((_, j) => (
              <div key={j} className="flex items-center gap-3 py-2">
                <Skeleton className="h-4 w-16" />
                <Skeleton className="h-3 w-24" />
                <Skeleton className="h-4 w-14 ml-auto" />
              </div>
            ))}
          </Card>
        ))}
      </div>
    );
  }

  if (error) {
    return (
      <div className="rounded-lg border border-red-500/30 bg-red-500/10 p-4 w-full max-w-3xl mx-auto">
        <p className="text-sm font-semibold text-red-400 mb-1">Could not load market movers</p>
        <p className="text-xs text-[#6b7f8e]">
          {(error as Error)?.message || "The backend may be unreachable."}
        </p>
      </div>
    );
  }

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 gap-4 w-full max-w-3xl mx-auto">
      <Card className="p-4">
        <p className="text-xs font-semibold text-[#84cc16] mb-3 flex items-center gap-1.5">
          <ArrowUpRight className="h-3.5 w-3.5" /> Top Gainers
        </p>
        <MoverList movers={data?.gainers ?? []} type="gainer" />
      </Card>
      <Card className="p-4">
        <p className="text-xs font-semibold text-red-400 mb-3 flex items-center gap-1.5">
          <ArrowDownRight className="h-3.5 w-3.5" /> Top Losers
        </p>
        <MoverList movers={data?.losers ?? []} type="loser" />
      </Card>
    </div>
  );
}
