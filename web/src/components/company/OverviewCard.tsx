"use client";

import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { getSignalColor, getSignalBg, computeRegime } from "@/lib/utils";
import {
  DollarSign, TrendingUp, Users, Building2, Activity, Globe,
  AlertCircle, Minus,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";

// ─── Signal verdict computation (pure functions, easily testable) ──

interface VerdictResult {
  label: string;      // "Expensive", "Cheap", "Fair"
  detail: string;     // plain English explanation
  hasData: boolean;   // false when API returned no data
}

function computeValuationVerdict(
  healthData: Record<string, unknown> | undefined,
  dcfData: Record<string, unknown> | undefined,
  intrinsicData: Record<string, unknown> | undefined,
): VerdictResult {
  const price = (healthData?.price as number) ?? null;
  const fairValue = (dcfData?.fair_value_per_share as number) ?? (dcfData?.fair_value_with_cash as number) ?? null;
  const grahamNumber = (intrinsicData?.breakdown as Record<string, unknown>)?.graham_number as number | undefined;

  if (price == null) return { label: "N/A", detail: "Price data unavailable", hasData: false };
  if (fairValue == null && !grahamNumber) return { label: "N/A", detail: "Valuation data unavailable", hasData: false };

  // Use DCF fair value if available, fall back to Graham number
  const reference = fairValue ?? grahamNumber;
  if (reference == null || reference <= 0) return { label: "N/A", detail: "Valuation data unavailable", hasData: false };

  const ratio = price / reference;

  if (ratio > 1.3) {
    return {
      label: "Expensive",
      detail: `Trading ${Math.round((ratio - 1) * 100)}% above estimated fair value`,
      hasData: true,
    };
  }
  if (ratio < 0.85) {
    return {
      label: "Cheap",
      detail: `Trading ${Math.round((1 - ratio) * 100)}% below estimated fair value`,
      hasData: true,
    };
  }
  return {
    label: "Fair",
    detail: `Trading near estimated fair value (${Math.round(ratio * 100)}% of value)`,
    hasData: true,
  };
}

function computeWallStreetVerdict(sentiment: Record<string, unknown> | undefined): VerdictResult {
  const analyst = sentiment?.analyst as Record<string, unknown> | undefined;
  if (!analyst) return { label: "No data", detail: "No analyst coverage", hasData: false };

  const buy = (analyst.buy as number) ?? 0;
  const hold = (analyst.hold as number) ?? 0;
  const sell = (analyst.sell as number) ?? 0;
  const total = buy + hold + sell;

  if (total === 0) return { label: "No data", detail: "No analyst ratings", hasData: false };

  const targets = sentiment?.price_targets as Record<string, unknown> | undefined;
  const avgTarget = targets?.average as number | undefined;
  const numAnalysts = sentiment?.num_analysts as number | undefined;

  if (buy > sell * 1.5) {
    const detail = `${buy}B / ${hold}H / ${sell}S` +
      (avgTarget != null ? ` · avg target $${avgTarget.toFixed(2)}` : "") +
      (numAnalysts != null ? ` · ${numAnalysts} analysts` : "");
    return { label: "Bullish", detail, hasData: true };
  }
  if (sell > buy) {
    const detail = `${buy}B / ${hold}H / ${sell}S` +
      (avgTarget != null ? ` · avg target $${avgTarget.toFixed(2)}` : "") +
      (numAnalysts != null ? ` · ${numAnalysts} analysts` : "");
    return { label: "Bearish", detail, hasData: true };
  }
  const detail = `${buy}B / ${hold}H / ${sell}S` +
    (avgTarget != null ? ` · avg target $${avgTarget.toFixed(2)}` : "") +
    (numAnalysts != null ? ` · ${numAnalysts} analysts` : "");
  return { label: "Mixed", detail, hasData: true };
}

function computeInsiderVerdict(insider: Record<string, unknown> | undefined): VerdictResult {
  const trades = insider?.insider as Record<string, unknown>[] | undefined;
  if (!trades || trades.length === 0) return { label: "No data", detail: "No recent insider activity", hasData: false };

  let netShares = 0;
  let totalValue = 0;
  for (const t of trades) {
    const type = (t.transaction as string) ?? "";
    const shares = (t.shares as number) ?? 0;
    const value = (t.value as number) ?? 0;
    if (type.toLowerCase().includes("purchase") || type.toLowerCase().includes("buy")) {
      netShares += shares;
      totalValue += value;
    } else {
      netShares -= shares;
      totalValue -= value;
    }
  }

  if (Math.abs(netShares) < 100 && trades.length < 3) {
    return { label: "No data", detail: "Minimal insider activity", hasData: false };
  }

  if (netShares > 0) {
    const absValue = Math.abs(totalValue);
    const detail = absValue > 1e6
      ? `Net buying $${(absValue / 1e6).toFixed(1)}M in shares`
      : `Net buying ${Math.abs(netShares).toLocaleString()} shares`;
    return { label: "Buying", detail, hasData: true };
  }
  if (netShares < 0) {
    const absValue = Math.abs(totalValue);
    const detail = absValue > 1e6
      ? `Net selling $${(absValue / 1e6).toFixed(1)}M in shares`
      : `Net selling ${Math.abs(netShares).toLocaleString()} shares`;
    return { label: "Selling", detail, hasData: true };
  }
  return { label: "Neutral", detail: "Balanced insider activity", hasData: true };
}

function computeSmartMoneyVerdict(inst: Record<string, unknown> | undefined): VerdictResult {
  const verdict = inst?.verdict as string | undefined;
  const holders = inst?.holders as Record<string, unknown>[] | undefined;

  if (!holders || holders.length === 0) return { label: "No data", detail: "No institutional data", hasData: false };

  const topHolders = holders.slice(0, 3).map(h => (h.name as string) ?? "").filter(Boolean).join(", ");
  const detail = topHolders || `${holders.length} holders`;

  if (!verdict) return { label: "Neutral", detail, hasData: true };

  const lower = verdict.toLowerCase();
  if (lower.includes("accumulat") || lower.includes("bullish") || lower.includes("buy")) {
    return { label: "Accumulating", detail, hasData: true };
  }
  if (lower.includes("distribut") || lower.includes("bearish") || lower.includes("sell")) {
    return { label: "Distributing", detail, hasData: true };
  }
  return { label: "Neutral", detail, hasData: true };
}

function computeMomentumVerdict(
  priceGrowth: Record<string, unknown> | undefined,
  healthData: Record<string, unknown> | undefined,
): VerdictResult {
  const g3m = priceGrowth?.growth_3m as number | undefined;
  const g6m = priceGrowth?.growth_6m as number | undefined;
  const g12m = priceGrowth?.growth_12m as number | undefined;

  // Fall back to change_pct from health data
  const changePct = healthData?.change_pct as number | undefined;

  if (g3m == null && g6m == null && g12m == null) {
    if (changePct != null) {
      const label = changePct > 5 ? "Strong" : changePct < -5 ? "Weak" : "Flat";
      return { label, detail: `Today: ${changePct >= 0 ? "+" : ""}${changePct.toFixed(2)}%`, hasData: true };
    }
    return { label: "No data", detail: "Price history unavailable", hasData: false };
  }

  const periods = [g3m, g6m, g12m].filter((v): v is number => v != null);
  if (periods.length === 0) return { label: "No data", detail: "Price history unavailable", hasData: false };

  const positive = periods.filter(p => p > 0).length;
  const negative = periods.filter(p => p < 0).length;
  const avgGrowth = periods.reduce((a, b) => a + b, 0) / periods.length;

  if (positive === periods.length) {
    return { label: "Strong", detail: `3M: ${formatPctShort(g3m)} · 6M: ${formatPctShort(g6m)} · 12M: ${formatPctShort(g12m)}`, hasData: true };
  }
  if (negative === periods.length) {
    return { label: "Weak", detail: `3M: ${formatPctShort(g3m)} · 6M: ${formatPctShort(g6m)} · 12M: ${formatPctShort(g12m)}`, hasData: true };
  }
  return { label: "Mixed", detail: `3M: ${formatPctShort(g3m)} · 6M: ${formatPctShort(g6m)} · 12M: ${formatPctShort(g12m)}`, hasData: true };
}

function formatPctShort(value: number | undefined): string {
  if (value == null) return "N/A";
  return `${value >= 0 ? "+" : ""}${value.toFixed(1)}%`;
}

// ─── Signal Card Component ───────────────────────────────────────

interface SignalCardProps {
  icon: LucideIcon;
  title: string;
  verdict: string;
  detail: string;
  hasData: boolean;
}

function SignalCard({ icon: Icon, title, verdict, detail, hasData }: SignalCardProps) {
  if (!hasData) {
    return (
      <div className="rounded-xl border border-[#1e2d3a] bg-[#111922] p-4 opacity-60">
        <div className="flex items-center gap-2 mb-2">
          <Icon className="h-4 w-4 text-[#6b7f8e]" />
          <span className="text-xs text-[#6b7f8e]">{title}</span>
        </div>
        <p className="text-lg font-semibold text-[#6b7f8e]">—</p>
        <p className="text-xs text-[#4a6070] mt-1">{detail}</p>
      </div>
    );
  }

  return (
    <div className={`rounded-xl border p-4 ${getSignalBg(verdict)}`}>
      <div className="flex items-center gap-2 mb-2">
        <Icon className={`h-4 w-4 ${getSignalColor(verdict)}`} />
        <span className="text-xs text-[#6b7f8e]">{title}</span>
      </div>
      <p className={`text-lg font-semibold ${getSignalColor(verdict)}`}>{verdict}</p>
      <p className="text-xs text-[#6b7f8e] mt-1">{detail}</p>
    </div>
  );
}

// ─── Summary Line ────────────────────────────────────────────────

interface SummaryLineProps {
  ticker: string;
  valuation: VerdictResult;
  wallStreet: VerdictResult;
  insiders: VerdictResult;
  smartMoney: VerdictResult;
  momentum: VerdictResult;
  regime: string;
}

function SummaryLine({ ticker, valuation, wallStreet, insiders, smartMoney, momentum, regime }: SummaryLineProps) {
  const clauses: string[] = [];

  if (valuation.hasData) clauses.push(`is ${valuation.label.toLowerCase()}`);
  if (insiders.hasData) clauses.push(`insiders are ${insiders.label.toLowerCase()}`);
  if (momentum.hasData) clauses.push(`momentum is ${momentum.label.toLowerCase()}`);

  let wallStreetStr = "";
  if (wallStreet.hasData) {
    const detail = wallStreet.detail;
    wallStreetStr = `Wall Street is ${wallStreet.label.toLowerCase()} (${detail})`;
  }

  if (clauses.length === 0 && !wallStreetStr) {
    return <p className="text-sm text-[#6b7f8e]">Limited data available for {ticker}.</p>;
  }

  const summary = clauses.length > 0
    ? `${ticker} ${clauses.join(", ")}`
    : "";

  const extra = [wallStreetStr, `Market regime: ${regime}`].filter(Boolean);

  return (
    <p className="text-sm text-[#c8d8e4] leading-relaxed">
      {summary}
      {summary && extra.length > 0 && ". "}
      {extra.join(". ")}
      {extra.length > 0 && "."}
    </p>
  );
}

// ── Main Overview Card ──────────────────────────────────────────

interface OverviewCardProps {
  ticker: string;
  healthData: Record<string, unknown> | undefined;
  dcfData: Record<string, unknown> | undefined;
  intrinsicData: Record<string, unknown> | undefined;
  sentiment: Record<string, unknown> | undefined;
  institutional: Record<string, unknown> | undefined;
  insider: Record<string, unknown> | undefined;
  priceGrowth: Record<string, unknown> | undefined;
  macro: Record<string, unknown> | undefined;
  indices: { name: string; change_pct: number }[] | undefined;
  isLoading: boolean;
}

export function OverviewCard({
  ticker,
  healthData, dcfData, intrinsicData,
  sentiment, institutional, insider,
  priceGrowth, macro, indices,
  isLoading,
}: OverviewCardProps) {
  if (isLoading) {
    return (
      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-base">Overview</CardTitle>
          <CardDescription>Loading analysis…</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3">
            {[1, 2, 3, 4, 5, 6].map((i) => (
              <div key={i} className="rounded-xl border border-[#1e2d3a] bg-[#111922] p-4">
                <Skeleton className="h-4 w-20 mb-3" />
                <Skeleton className="h-6 w-16 mb-2" />
                <Skeleton className="h-3 w-full" />
              </div>
            ))}
          </div>
        </CardContent>
      </Card>
    );
  }

  // Compute verdicts
  const valuation = computeValuationVerdict(healthData, dcfData, intrinsicData);
  const wallStreet = computeWallStreetVerdict(sentiment);
  const insiders = computeInsiderVerdict(insider);
  const smartMoney = computeSmartMoneyVerdict(institutional);
  const momentum = computeMomentumVerdict(priceGrowth, healthData);
  const regime = computeRegime(macro, indices);

  return (
    <Card>
      <CardHeader className="pb-2">
        <CardTitle className="text-base">Overview</CardTitle>
        <CardDescription>Plain-English analysis of {ticker}</CardDescription>
      </CardHeader>
      <CardContent>
        {/* Signal cards */}
        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3">
          <SignalCard
            icon={DollarSign}
            title="Valuation"
            verdict={valuation.label}
            detail={valuation.detail}
            hasData={valuation.hasData}
          />
          <SignalCard
            icon={TrendingUp}
            title="Wall Street"
            verdict={wallStreet.label}
            detail={wallStreet.detail}
            hasData={wallStreet.hasData}
          />
          <SignalCard
            icon={Users}
            title="Insiders"
            verdict={insiders.label}
            detail={insiders.detail}
            hasData={insiders.hasData}
          />
          <SignalCard
            icon={Building2}
            title="Smart Money"
            verdict={smartMoney.label}
            detail={smartMoney.detail}
            hasData={smartMoney.hasData}
          />
          <SignalCard
            icon={Activity}
            title="Momentum"
            verdict={momentum.label}
            detail={momentum.detail}
            hasData={momentum.hasData}
          />
          <SignalCard
            icon={Globe}
            title="Regime"
            verdict={regime.verdict === "Unknown" ? "N/A" : regime.verdict}
            detail={
              regime.vixVerdict && regime.spTrend
                ? `VIX: ${regime.vixVerdict} · S&P: ${regime.spTrend}`
                : regime.vixVerdict
                  ? `VIX: ${regime.vixVerdict}`
                  : regime.spTrend
                    ? `S&P: ${regime.spTrend}`
                    : "No macro data"
            }
            hasData={regime.verdict !== "Unknown"}
          />
        </div>

        {/* Summary line */}
        <div className="mt-4 pt-3 border-t border-[#1e2d3a]">
          <SummaryLine
            ticker={ticker}
            valuation={valuation}
            wallStreet={wallStreet}
            insiders={insiders}
            smartMoney={smartMoney}
            momentum={momentum}
            regime={regime.verdict}
          />
        </div>
      </CardContent>
    </Card>
  );
}
