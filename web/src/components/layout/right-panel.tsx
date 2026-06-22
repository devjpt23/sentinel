"use client";

import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api-client";
import { useMarketIndices } from "@/hooks/use-market-data";
import { useUser } from "@/hooks/use-watchlist";
import { ArrowUpRight, ArrowDownRight, TrendingUp, TrendingDown } from "lucide-react";

function SectionTitle({ children }: { children: React.ReactNode }) {
  return (
    <h3 className="px-4 py-3 text-xs font-semibold uppercase tracking-wider text-[#6b7f8e] border-b border-[#1e2d3a]">
      {children}
    </h3>
  );
}

function NotificationsSection({ userId }: { userId: number }) {
  const { data, isLoading } = useQuery({
    queryKey: ["notifications", userId, 5],
    queryFn: () => api.get<Record<string, unknown>>(`/api/notifications/${userId}`, { params: { limit: 5 } }),
    retry: false,
  });

  const items = (data?.notifications ?? data?.items ?? []) as { message?: string; created_at?: string; severity?: string }[];

  if (isLoading) return null;

  return (
    <div>
      <SectionTitle>Notifications</SectionTitle>
      <div className="px-4 py-2 space-y-2">
        {items.length > 0 ? items.map((item, i) => (
          <div key={i} className="flex items-start gap-2">
            <div className="mt-1 h-1.5 w-1.5 rounded-full bg-[#84cc16] shrink-0" />
            <div className="min-w-0">
              <p className="text-xs text-[#c8d8e4] leading-snug">{item.message ?? "Notification"}</p>
              {item.created_at && (
                <p className="text-[10px] text-[#3a5570] mt-0.5">{item.created_at}</p>
              )}
            </div>
          </div>
        )) : (
          <p className="text-xs text-[#6b7f8e]">No notifications</p>
        )}
      </div>
    </div>
  );
}

function MarketMoversSection() {
  const { data: indices, isLoading } = useMarketIndices();

  if (isLoading) return null;

  const sorted = [...(indices ?? [])].sort((a, b) => (b.change_pct ?? 0) - (a.change_pct ?? 0));
  const gainer = sorted[0];
  const loser = sorted[sorted.length - 1];

  return (
    <div>
      <SectionTitle>Market Movers</SectionTitle>
      <div className="px-4 py-2 space-y-2">
        {gainer && (
          <div className="flex items-center justify-between">
            <div>
              <p className="text-xs font-medium text-[#c8d8e4]">{gainer.name}</p>
              <p className="text-[10px] text-[#6b7f8e]">Top Gainer</p>
            </div>
            <div className="flex items-center gap-1 text-xs font-medium text-[#84cc16]">
              <ArrowUpRight className="h-3 w-3" />
              {((gainer.change_pct ?? 0) * 100).toFixed(2)}%
            </div>
          </div>
        )}
        {loser && (
          <div className="flex items-center justify-between">
            <div>
              <p className="text-xs font-medium text-[#c8d8e4]">{loser.name}</p>
              <p className="text-[10px] text-[#6b7f8e]">Top Loser</p>
            </div>
            <div className="flex items-center gap-1 text-xs font-medium text-red-400">
              <ArrowDownRight className="h-3 w-3" />
              {((loser.change_pct ?? 0) * 100).toFixed(2)}%
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

function MarketPulseSection() {
  const { data: indices } = useMarketIndices();

  const sp500 = indices?.find((i) => i.name === "S&P 500");
  const isUp = (sp500?.change_pct ?? 0) >= 0;

  return (
    <div>
      <SectionTitle>Market Pulse</SectionTitle>
      <div className="px-4 py-3">
        <div className="flex items-center gap-3">
          {isUp ? (
            <div className="h-10 w-10 rounded-full bg-[#84cc16]/20 flex items-center justify-center">
              <TrendingUp className="h-5 w-5 text-[#84cc16]" />
            </div>
          ) : (
            <div className="h-10 w-10 rounded-full bg-red-500/20 flex items-center justify-center">
              <TrendingDown className="h-5 w-5 text-red-400" />
            </div>
          )}
          <div>
            <p className="text-sm font-semibold text-[#f0f4f0]">
              {isUp ? "Bullish" : "Bearish"}
            </p>
            <p className="text-xs text-[#6b7f8e]">
              S&P 500 {(sp500?.change_pct ?? 0) >= 0 ? "up" : "down"}{" "}
              {Math.abs((sp500?.change_pct ?? 0) * 100).toFixed(2)}% today
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}

export function RightPanel() {
  const { data: userData } = useUser();
  const userId = userData?.id ?? 0;
  return (
    <aside className="fixed right-0 top-0 z-30 flex h-screen w-72 flex-col border-l border-[#1e2d3a] bg-[#0d1319] overflow-y-auto">
      <NotificationsSection userId={userId} />
      <MarketMoversSection />
      <MarketPulseSection />
    </aside>
  );
}
