"use client";

import { useRouter } from "next/navigation";
import Link from "next/link";
import { Card, CardContent } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { HealthCard } from "@/components/shared/HealthCard";
import { MetricCard } from "@/components/shared/MetricCard";
import { DonutChart } from "@/components/charts/DonutChart";
import { MiniAreaChart } from "@/components/charts/MiniAreaChart";
import { useMarketIndices, useMacroIndicators, useMarketNews } from "@/hooks/use-market-data";
import { useEnrichedWatchlist } from "@/hooks/use-watchlist";
import { formatPrice, formatPct, formatRelativeTime } from "@/lib/utils";
import {
  ArrowUpRight,
  ArrowDownRight,
  Eye,
  Newspaper,
  ExternalLink,
  DollarSign,
  Activity,
  TrendingUp,
} from "lucide-react";

export default function DashboardPage() {
  const router = useRouter();
  const { data: indices, isLoading: indicesLoading } = useMarketIndices();
  const { data: macro, isLoading: macroLoading } = useMacroIndicators();
  const { data: news, isLoading: newsLoading } = useMarketNews(5);
  const { data: enrichedItems, isLoading: wlLoading } = useEnrichedWatchlist();

  // Filter out error entries for display
  const wlItems = (enrichedItems ?? []).filter((i) => !i.error);

  // Resolve indices for metric cards
  const sp500 = indices?.find((i) => i.name === "S&P 500");
  const nasdaq = indices?.find((i) => i.name === "NASDAQ");
  const vix = macro?.vix?.value;
  const dxy = macro?.dollar?.value;

  // Sector breakdown for donut
  const sectorData = wlItems.reduce<Record<string, number>>((acc, item) => {
    acc[item.sector] = (acc[item.sector] || 0) + 1;
    return acc;
  }, {});
  const donutData = Object.entries(sectorData).map(([name, value]) => ({ name, value }));

  // Mini area chart placeholder data
  const areaData = Array.from({ length: 12 }, (_, i) => ({
    value: 100 + Math.sin(i * 0.5) * 20 + i * 5 + Math.random() * 10,
  }));

  return (
    <div className="space-y-4">
      {/* Row 1: 4 Metric Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {indicesLoading ? (
          <>
            {[1, 2].map((i) => (
              <Card key={i} className="p-4">
                <Skeleton className="h-3 w-24 mb-2" />
                <Skeleton className="h-8 w-32" />
                <Skeleton className="h-3 w-16 mt-1" />
              </Card>
            ))}
          </>
        ) : (
          <>
            <MetricCard
              label="S&P 500"
              value={sp500 ? formatPrice(sp500.value) : "—"}
              change={sp500?.change_pct}
              icon={TrendingUp}
            />
            <MetricCard
              label="NASDAQ"
              value={nasdaq ? formatPrice(nasdaq.value) : "—"}
              change={nasdaq?.change_pct}
              icon={TrendingUp}
            />
            <MetricCard
              label="VIX"
              value={vix !== undefined ? vix.toFixed(2) : "—"}
              icon={Activity}
            />
            <MetricCard
              label="DXY"
              value={dxy !== undefined ? dxy.toFixed(2) : "—"}
              icon={DollarSign}
            />
          </>
        )}
      </div>

      {/* Row 2: Donut chart + Mini stats */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        {/* Sector Donut */}
        <Card className="p-4 lg:col-span-1">
          <p className="text-xs text-[#6b7f8e] mb-3">Sector Allocation</p>
          <div className="flex items-center gap-4">
            <DonutChart data={donutData} size={140} thickness={22} />
            <div className="space-y-1.5 flex-1">
              {donutData.map((d) => (
                <div key={d.name} className="flex items-center justify-between text-xs">
                  <span className="text-[#c8d8e4]">{d.name}</span>
                  <span className="text-[#6b7f8e]">{d.value}</span>
                </div>
              ))}
            </div>
          </div>
        </Card>

        {/* Macro / Health Card with area chart */}
        <Card className="p-4 lg:col-span-1">
          <div className="flex items-center justify-between mb-2">
            <p className="text-xs text-[#6b7f8e]">Macro Trend</p>
            <span className="text-xs text-[#84cc16]">+12.4%</span>
          </div>
          <p className="text-lg font-bold text-[#f0f4f0] mb-2">
            {macro?.credit?.value !== null && macro?.credit?.value !== undefined
              ? `Spread: ${macro.credit.value.toFixed(2)}`
              : "Credit Spread"}
          </p>
          <MiniAreaChart data={areaData} />
        </Card>

        {/* Avg Health Score */}
        <Card className="p-4 lg:col-span-1">
          <div className="flex items-center justify-between mb-2">
            <p className="text-xs text-[#6b7f8e]">Avg Health Score</p>
          </div>
          <p className="text-2xl font-bold text-[#84cc16] mb-2">
            {wlItems.length > 0
              ? Math.round(wlItems.reduce((s, i) => s + i.healthScore, 0) / wlItems.length)
              : "—"}
          </p>
          <p className="text-xs text-[#6b7f8e]">
            Across {wlItems.length} watchlisted companies
          </p>
          <div className="mt-3 flex gap-2">
            {wlItems.slice(0, 4).map((item) => (
              <button
                key={item.ticker}
                onClick={() => router.push(`/company/${item.ticker}`)}
                className="flex items-center gap-1 rounded-md bg-[#1a2a38] px-2 py-1 text-xs text-[#c8d8e4] hover:bg-[#2a3f52] transition-colors"
              >
                <span className="font-mono font-semibold">{item.ticker}</span>
                <span className={item.change_pct >= 0 ? "text-[#84cc16]" : "text-red-400"}>
                  {formatPct(item.change_pct)}
                </span>
              </button>
            ))}
          </div>
        </Card>
      </div>

      {/* Row 3: Watchlist table + Market News */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        {/* Watchlist Table */}
        <Card className="p-4 lg:col-span-2">
          <div className="flex items-center justify-between mb-4">
            <p className="text-sm font-semibold text-[#f0f4f0]">Watchlist</p>
            <Link href="/watchlist" className="text-xs text-[#84cc16] hover:text-[#65a30d] flex items-center gap-1 transition-colors">
              View all <Eye className="h-3 w-3" />
            </Link>
          </div>
          <div className="space-y-1">
            {wlLoading ? (
              Array.from({ length: 5 }).map((_, i) => (
                <div key={i} className="flex items-center gap-4 py-2">
                  <Skeleton className="h-8 w-8 rounded-full" />
                  <Skeleton className="h-4 w-20" />
                  <Skeleton className="h-4 w-16 ml-auto" />
                </div>
              ))
            ) : (
              wlItems.map((item) => (
                <button
                  key={item.ticker}
                  onClick={() => router.push(`/company/${item.ticker}`)}
                  className="flex items-center gap-4 w-full py-2 px-2 rounded-lg hover:bg-[#1a2a38]/50 transition-colors text-left"
                >
                  <div className="h-8 w-8 rounded-full bg-[#1a2a38] flex items-center justify-center text-xs font-bold text-[#84cc16]">
                    {item.ticker.slice(0, 2)}
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-semibold text-[#f0f4f0]">{item.ticker}</p>
                    <p className="text-xs text-[#6b7f8e] truncate">{item.name}</p>
                  </div>
                  <div className="text-right">
                    <p className="text-sm font-mono text-[#c8d8e4]">{formatPrice(item.price)}</p>
                    <p className={`text-xs font-mono ${item.change_pct >= 0 ? "text-[#84cc16]" : "text-red-400"}`}>
                      {item.change_pct >= 0 ? "+" : ""}{formatPct(item.change_pct)}
                    </p>
                  </div>
                  <div className="flex items-center gap-1">
                    <span className={`inline-flex items-center rounded-full border px-2 py-0.5 text-[10px] font-semibold ${
                      item.healthScore >= 70
                        ? "border-[#84cc16]/30 bg-[#84cc16]/20 text-[#84cc16]"
                        : item.healthScore >= 40
                        ? "border-yellow-500/30 bg-yellow-500/20 text-yellow-400"
                        : "border-red-500/30 bg-red-500/20 text-red-400"
                    }`}>
                      {item.healthScore}
                    </span>
                  </div>
                </button>
              ))
            )}
          </div>
        </Card>

        {/* Market News */}
        <Card className="p-4 lg:col-span-1">
          <div className="flex items-center justify-between mb-4">
            <p className="text-sm font-semibold text-[#f0f4f0]">Market News</p>
          </div>
          <div className="space-y-3">
            {newsLoading ? (
              Array.from({ length: 4 }).map((_, i) => (
                <div key={i} className="flex gap-3">
                  <Skeleton className="h-3.5 flex-1" />
                </div>
              ))
            ) : news && news.length > 0 ? (
              (news as any[]).slice(0, 5).map((item, i) => (
                <a
                  key={i}
                  href={item.url || "#"}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="flex items-start gap-3 group"
                >
                  <div className="mt-1 h-1.5 w-1.5 rounded-full bg-[#84cc16] shrink-0" />
                  <div className="min-w-0">
                    <p className="text-xs text-[#c8d8e4] leading-snug group-hover:text-[#f0f4f0] transition-colors truncate">
                      {item.title}
                    </p>
                    <div className="flex items-center gap-2 mt-1">
                      <span className="text-[10px] text-[#6b7f8e]">{item.publisher}</span>
                      <span className="text-[10px] text-[#3a5570]">•</span>
                      <span className="text-[10px] text-[#6b7f8e]">
                        {formatRelativeTime(item.published)}
                      </span>
                    </div>
                  </div>
                </a>
              ))
            ) : (
              <p className="text-xs text-[#6b7f8e]">No market news available.</p>
            )}
          </div>
        </Card>
      </div>
    </div>
  );
}
