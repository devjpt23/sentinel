"use client";

import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api-client";
import { formatPct } from "@/lib/utils";

export function MarqueeTicker() {
  const { data } = useQuery({
    queryKey: ["market-indices"],
    queryFn: () => api.get<{ indices: Array<{ name: string; price: number; change_pct: number | null }> }>("/api/market/indices"),
    refetchInterval: 60000,
  });

  const indices = data?.indices ?? [];

  return (
    <div className="overflow-hidden border-b border-[#1e2d3a] bg-[#0a0e13] py-1">
      <div className="flex animate-marquee whitespace-nowrap">
        {indices.map((idx, i) => (
          <span key={i} className="mx-4 text-xs text-[#6b7f8e]">
            <span className="text-[#c8d8e4] font-medium">{idx.name}</span>
            {" "}
            <span>{idx.price.toLocaleString()}</span>
            {" "}
            <span className={idx.change_pct != null && idx.change_pct >= 0 ? "text-[#84cc16]" : "text-red-400"}>
              {formatPct(idx.change_pct)}
            </span>
          </span>
        ))}
      </div>
    </div>
  );
}
