"use client";

import { useState } from "react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { Tabs } from "@/components/ui/tabs";
import { Button } from "@/components/ui/button";
import { Slider } from "@/components/ui/slider";
import type { UTCTimestamp } from "lightweight-charts";
import { ScoreBadge } from "@/components/shared/ScoreBadge";
import { VerdictBadge } from "@/components/shared/VerdictBadge";
import { RiskBadge } from "@/components/shared/RiskBadge";
import { PriceChart } from "@/components/charts/PriceChart";
import { useHealth, useIntrinsic, useRisk, useFinancials, useDcf, usePriceHistory, useSentiment, useInstitutional, useInsider, usePriceGrowth, useMacro, useIndices } from "@/hooks/use-company-data";
import { OverviewCard } from "@/components/company/OverviewCard";
import {
  formatCurrency, formatPercent, formatPrice, formatPct, formatRelativeTime,
  getHealthBg, getZScoreZoneColor, getSensitivityCellColor,
} from "@/lib/utils";
import {
  ArrowLeft, TrendingUp, TrendingDown, AlertTriangle, Shield,
  DollarSign, BarChart3, FileText, ChevronDown, ChevronUp, Network, Newspaper, ExternalLink,
} from "lucide-react";

type PricePeriod = "1mo" | "3mo" | "6mo" | "1y" | "2y";

// Type helpers for API responses (Record<string, unknown>)
const num = (v: unknown): number => (typeof v === "number" ? v : 0);
const str = (v: unknown): string => (typeof v === "string" ? v : "");

export default function CompanyDeepDivePage() {
  const params = useParams();
  const ticker = (params?.ticker as string)?.toUpperCase() ?? "";
  const router = useRouter();

  const [activeTab, setActiveTab] = useState("financials");
  const [pricePeriod, setPricePeriod] = useState<PricePeriod>("1y");

  const { data: healthData, isLoading: healthLoading, error: healthError } = useHealth(ticker);
  const { data: intrinsicData, isLoading: intrinsicLoading } = useIntrinsic(ticker);
  const { data: riskData, isLoading: riskLoading } = useRisk(ticker);
  const { data: financialsData, isLoading: financialsLoading } = useFinancials(ticker);

  // Price history for candlestick chart
  const { data: priceHistoryData, isLoading: priceHistoryLoading, error: priceError } = usePriceHistory(ticker, pricePeriod);

  // DCF slider state
  const [revenueGrowth, setRevenueGrowth] = useState(10);
  const [terminalGrowth, setTerminalGrowth] = useState(3);
  const [discountRate, setDiscountRate] = useState(10);
  const [marginImprovement, setMarginImprovement] = useState(0);

  const { data: dcfData, isLoading: dcfLoading } = useDcf(ticker, {
    revenue_growth_5yr: revenueGrowth / 100,
    terminal_growth: terminalGrowth / 100,
    discount_rate: discountRate / 100,
    margin_improvement: marginImprovement / 100,
  });

  // Overview card data
  const { data: sentimentData } = useSentiment(ticker);
  const { data: institutionalData } = useInstitutional(ticker);
  const { data: insiderData } = useInsider(ticker);
  const { data: priceGrowthData } = usePriceGrowth(ticker);
  const { data: macroData } = useMacro();
  const { data: indicesData } = useIndices();

  // Extract typed values from health data
  const hScore = num(healthData?.score);
  const hName = str(healthData?.name);
  const hSector = str(healthData?.sector);
  const hPrice = num(healthData?.price);
  const hChange = num(healthData?.change);
  const hChangePct = num(healthData?.change_pct);
  const hVerdict = str(healthData?.verdict);
  const hFscore = num(healthData?.fscore);
  const hCriteria = (healthData?.criteria ?? []) as [string, boolean, string][];
  const hZscore = healthData?.zscore_score as number | undefined;
  const hZscoreZone = str(healthData?.zscore_zone);
  const hZscoreExpl = str(healthData?.zscore_explanation);
  const hZscoreX1 = num(healthData?.zscore_x1);
  const hZscoreX2 = num(healthData?.zscore_x2);
  const hZscoreX3 = num(healthData?.zscore_x3);
  const hZscoreX4 = num(healthData?.zscore_x4);

  // News from health endpoint (already fetched, deduped, and filtered server-side)
  type NewsItem = { title: string; summary: string; url: string; publisher: string; published: string };
  const newsItems = ((healthData?.news ?? []) as NewsItem[]).filter((n) => n.title);

  return (
    <div className="space-y-6">
      {/* Back button + Header */}
      <div className="flex items-center gap-4">
        <Button variant="ghost" size="icon" onClick={() => router.back()}>
          <ArrowLeft className="h-4 w-4" />
        </Button>
        <div className="flex-1">
          <div className="flex items-center gap-3">
            <h1 className="text-2xl font-bold">{ticker}</h1>
            {!healthLoading && <ScoreBadge score={hScore || 50} size="md" />}
          </div>
          <p className="text-sm text-[#6b7f8e]">
            {hName || "Company name"} • {hSector || "Sector"}
          </p>
        </div>
        <Link
          href={`/supply-chain/${ticker}`}
          className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-[#1e2d3a] text-xs text-[#6b7f8e] hover:text-[#84cc16] hover:border-[#84cc16]/30 transition-colors"
        >
          <Network className="h-3.5 w-3.5" />
          Supply Chain
        </Link>
        <div className="text-right">
          <div className="text-2xl font-bold">
            {healthLoading ? <Skeleton className="h-8 w-24 ml-auto" /> : formatPrice(hPrice)}
          </div>
          {!healthLoading && (
            <p className={`text-sm font-medium ${hChange >= 0 ? "text-emerald-400" : "text-red-400"}`}>
              {hChange >= 0 ? "+" : ""}{hChangePct.toFixed(2)}%
            </p>
          )}
        </div>
      </div>

      {/* API Error Banner */}
      {(healthError || priceError) && (
        <div className="rounded-lg border border-red-500/30 bg-red-500/10 p-4">
          <p className="text-sm font-semibold text-red-400 mb-1">Failed to load data</p>
          <p className="text-xs text-[#6b7f8e]">
            {(healthError as Error)?.message || (priceError as Error)?.message || "Check your connection or API key."}
          </p>
          <p className="text-xs text-[#4a6070] mt-2">
            Make sure the Flask backend is running on port 5252 with CORS_ORIGINS including http://localhost:3000.
          </p>
        </div>
      )}

      {/* Quick badges */}
      {!healthLoading && !healthError && (
        <div className="flex gap-3">
          {hVerdict && <VerdictBadge verdict={hVerdict || "Unknown"} />}
          {riskData && <RiskBadge label={str(riskData.label) || "Medium"} />}
          <Badge variant="outline" className="text-xs">
            F-Score: {hFscore || "N/A"}/9
          </Badge>
        </div>
      )}

      {/* Overview Card - plain-English signals + regime detector */}
      <OverviewCard
        ticker={ticker}
        healthData={healthData as Record<string, unknown> | undefined}
        dcfData={dcfData as Record<string, unknown> | undefined}
        intrinsicData={intrinsicData as Record<string, unknown> | undefined}
        sentiment={sentimentData as Record<string, unknown> | undefined}
        institutional={institutionalData as Record<string, unknown> | undefined}
        insider={insiderData as Record<string, unknown> | undefined}
        priceGrowth={priceGrowthData as Record<string, unknown> | undefined}
        macro={macroData as Record<string, unknown> | undefined}
        indices={indicesData as { name: string; change_pct: number }[] | undefined}
        isLoading={healthLoading}
      />

      {/* Price Chart */}
      <Card>
        <CardHeader className="pb-2">
          <div className="flex items-center justify-between">
            <CardTitle className="text-base">Price Chart</CardTitle>
            <div className="flex gap-1">
              {(["1mo", "3mo", "6mo", "1y", "2y"] as PricePeriod[]).map((p) => (
                <button
                  key={p}
                  onClick={() => setPricePeriod(p)}
                  className={`px-2 py-1 text-xs rounded-md transition-colors ${
                    p === pricePeriod
                      ? "bg-[#2a3f52] text-white font-medium"
                      : "text-[#6b7f8e] hover:text-white hover:bg-[#1e2d3a]"
                  }`}
                >
                  {p}
                </button>
              ))}
            </div>
          </div>
        </CardHeader>
        <CardContent>
          {priceHistoryLoading ? (
            <div className="flex items-center justify-center h-[350px]">
              <Skeleton className="h-full w-full" />
            </div>
          ) : priceHistoryData?.candles && priceHistoryData.candles.length > 0 ? (
            <PriceChart candles={priceHistoryData.candles.map((c) => ({
              time: new Date(c.date).getTime() / 1000 as UTCTimestamp,
              open: c.open,
              high: c.high,
              low: c.low,
              close: c.close,
            }))} height={350} />
          ) : (
            <div className="flex items-center justify-center h-[350px] text-[#6b7f8e] text-sm">
              No price data available for {ticker}
            </div>
          )}
        </CardContent>
      </Card>

      {/* Latest News */}
      <Card>
        <CardHeader className="pb-2">
          <div className="flex items-center justify-between">
            <CardTitle className="text-base flex items-center gap-2">
              <Newspaper className="h-4 w-4" />
              Latest News
            </CardTitle>
            <Badge variant="outline" className="text-xs">
              {ticker}
            </Badge>
          </div>
        </CardHeader>
        <CardContent>
          {healthLoading ? (
            <div className="space-y-3">
              {Array.from({ length: 4 }).map((_, i) => (
                <Skeleton key={i} className="h-4 w-full" />
              ))}
            </div>
          ) : newsItems.length > 0 ? (
            <div className="space-y-3">
              {newsItems.map((item, i) => (
                <a
                  key={i}
                  href={item.url || "#"}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="flex items-start gap-3 group py-1"
                >
                  <div className="mt-1 h-1.5 w-1.5 rounded-full bg-[#84cc16] shrink-0" />
                  <div className="min-w-0 flex-1">
                    <p className="text-sm text-[#c8d8e4] leading-snug group-hover:text-[#f0f4f0] transition-colors line-clamp-2">
                      {item.title}
                    </p>
                    <div className="flex items-center gap-2 mt-1">
                      {item.publisher && (
                        <span className="text-[10px] text-[#6b7f8e]">{item.publisher}</span>
                      )}
                      {item.publisher && item.published && (
                        <span className="text-[10px] text-[#3a5570]">•</span>
                      )}
                      {item.published && (
                        <span className="text-[10px] text-[#6b7f8e]">
                          {formatRelativeTime(item.published)}
                        </span>
                      )}
                      <ExternalLink className="h-3 w-3 text-[#3a5570] opacity-0 group-hover:opacity-100 transition-opacity ml-auto" />
                    </div>
                  </div>
                </a>
              ))}
            </div>
          ) : (
            <p className="text-sm text-[#6b7f8e]">No news available for {ticker}.</p>
          )}
        </CardContent>
      </Card>

      {/* Tabs */}
      <Tabs
        tabs={[
          { id: "financials", label: "Financials" },
          { id: "valuation", label: "Valuation" },
          { id: "risk", label: "Risk" },
        ]}
        activeTab={activeTab}
        onTabChange={setActiveTab}
      />

      {/* Tab Content */}
      {activeTab === "financials" && (
        <FinancialsTab
          hFscore={hFscore} hCriteria={hCriteria}
          hZscore={hZscore} hZscoreZone={hZscoreZone} hZscoreExpl={hZscoreExpl}
          hZscoreX1={hZscoreX1} hZscoreX2={hZscoreX2} hZscoreX3={hZscoreX3} hZscoreX4={hZscoreX4}
          financialsData={financialsData}
          healthLoading={healthLoading}
          financialsLoading={financialsLoading}
        />
      )}
      {activeTab === "valuation" && (
        <ValuationTab
          dcfData={dcfData}
          intrinsicData={intrinsicData}
          dcfLoading={dcfLoading}
          intrinsicLoading={intrinsicLoading}
          revenueGrowth={revenueGrowth}
          setRevenueGrowth={setRevenueGrowth}
          terminalGrowth={terminalGrowth}
          setTerminalGrowth={setTerminalGrowth}
          discountRate={discountRate}
          setDiscountRate={setDiscountRate}
          marginImprovement={marginImprovement}
          setMarginImprovement={setMarginImprovement}
        />
      )}
      {activeTab === "risk" && (
        <RiskTab
          riskData={riskData}
          riskLoading={riskLoading}
        />
      )}
    </div>
  );
}

// ─── Financials Tab ────────────────────────────────────────────

function FinancialsTab({
  hFscore, hCriteria, hZscore, hZscoreZone, hZscoreExpl,
  hZscoreX1, hZscoreX2, hZscoreX3, hZscoreX4,
  financialsData, healthLoading, financialsLoading,
}: {
  hFscore: number; hCriteria: [string, boolean, string][];
  hZscore: number | undefined; hZscoreZone: string; hZscoreExpl: string;
  hZscoreX1: number; hZscoreX2: number; hZscoreX3: number; hZscoreX4: number;
  financialsData: Record<string, unknown> | undefined; healthLoading: boolean; financialsLoading: boolean;
}) {
  if (healthLoading || financialsLoading) {
    return (
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 mt-6">
        {[1, 2, 3, 4].map((i) => (
          <Card key={i} className="p-6">
            <Skeleton className="h-5 w-40 mb-4" />
            {[1, 2, 3].map((j) => (
              <Skeleton key={j} className="h-4 w-full mb-2" />
            ))}
          </Card>
        ))}
      </div>
    );
  }

  return (
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 mt-6">
      {/* Piotroski F-Score */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base flex items-center gap-2">
            <FileText className="h-4 w-4" />
            Piotroski F-Score: {hFscore}/9
          </CardTitle>
          <CardDescription>9-point financial strength checklist</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="space-y-3">
            {hCriteria.length > 0 ? hCriteria.map((c, i) => (
              <FscoreRow key={i} name={c[0]} passed={c[1]} explanation={c[2]} />
            )) : (
              <p className="text-sm text-[#6b7f8e]">No F-Score data available.</p>
            )}
          </div>
        </CardContent>
      </Card>

      {/* Altman Z-Score */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base flex items-center gap-2">
            <Shield className="h-4 w-4" />
            Altman Z-Score
          </CardTitle>
          <CardDescription>Bankruptcy risk assessment</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="space-y-3">
            <div className="flex items-center gap-3">
              <span className="text-3xl font-bold">
                {hZscore !== undefined ? hZscore : "N/A"}
              </span>
              <span className={getZScoreZoneColor(hZscoreZone || "Unknown")}>
                {hZscoreZone || "Unknown"}
              </span>
            </div>
            <p className="text-sm text-[#6b7f8e]">{hZscoreExpl}</p>
            {/* X components */}
            <div className="grid grid-cols-2 gap-3 mt-4">
              <ZscoreComponent label="Working Capital / Assets" value={hZscoreX1} />
              <ZscoreComponent label="Retained Earnings / Assets" value={hZscoreX2} />
              <ZscoreComponent label="EBIT / Assets" value={hZscoreX3} />
              <ZscoreComponent label="Market Equity / Liabilities" value={hZscoreX4} />
            </div>
            <p className="text-xs text-[#3a5570] mt-2">
              Z&apos;&apos; formula: 6.56×X1 + 3.26×X2 + 6.72×X3 + 1.05×X4
            </p>
          </div>
        </CardContent>
      </Card>

      {/* Income Statement */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Income Statement</CardTitle>
        </CardHeader>
        <CardContent>
          <FinancialTable data={financialsData?.income} />
        </CardContent>
      </Card>

      {/* Balance Sheet */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Balance Sheet</CardTitle>
        </CardHeader>
        <CardContent>
          <FinancialTable data={financialsData?.balance} />
        </CardContent>
      </Card>
    </div>
  );
}

function FscoreRow({ name, passed, explanation }: { name: string; passed: boolean; explanation: string }) {
  const [expanded, setExpanded] = useState(false);
  return (
    <div className="border-b border-[#1e2d3a] pb-2 last:border-0">
      <button
        onClick={() => setExpanded(!expanded)}
        className="flex items-center justify-between w-full text-left"
      >
        <div className="flex items-center gap-2">
          <span className={`text-sm ${passed ? "text-emerald-400" : "text-red-400"}`}>
            {passed ? "✓" : "✗"}
          </span>
          <span className="text-sm text-[#c8d8e4]">{name}</span>
        </div>
        {expanded ? <ChevronUp className="h-4 w-4 text-[#6b7f8e]" /> : <ChevronDown className="h-4 w-4 text-[#6b7f8e]" />}
      </button>
      {expanded && (
        <p className="text-xs text-[#6b7f8e] mt-1 ml-6">{explanation}</p>
      )}
    </div>
  );
}

function ZscoreComponent({ label, value }: { label: string; value: number | undefined }) {
  return (
    <div className="bg-[#1a2a38]/50 rounded-lg p-3">
      <p className="text-xs text-[#6b7f8e]">{label}</p>
      <p className="text-lg font-semibold">{value !== undefined ? value.toFixed(3) : "N/A"}</p>
    </div>
  );
}

function FinancialTable({ data }: { data: unknown }) {
  type Row = { label: string; values: Record<string, unknown> };
  const rows = data as Row[] | undefined;
  if (!rows || rows.length === 0) {
    return <p className="text-sm text-[#6b7f8e]">No data available.</p>;
  }

  // values is a record dict (one per row). Extract column keys from the first row.
  const firstValues = rows[0]?.values as Record<string, unknown> | undefined;
  const columns = firstValues ? Object.keys(firstValues) : [];

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-[#1e2d3a]">
            <th className="text-left py-1.5 text-[#6b7f8e] font-normal"></th>
            {columns.map((col) => (
              <th key={col} className="text-right py-1.5 text-[#6b7f8e] font-normal font-mono text-xs">
                {col}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => {
            const vals = row.values as Record<string, unknown>;
            return (
              <tr key={row.label} className="border-b border-[#1e2d3a]/50 last:border-0">
                <td className="py-1.5 text-[#c8d8e4]">{row.label}</td>
                {columns.map((col) => {
                  const v = (vals?.[col] ?? null) as number | null;
                  return (
                    <td key={col} className="text-right py-1.5 font-mono text-[#6b7f8e] text-xs">
                      {v !== null ? formatCurrency(v) : "N/A"}
                    </td>
                  );
                })}
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

// ─── Valuation Tab ─────────────────────────────────────────────

function ValuationTab({
  dcfData, intrinsicData, dcfLoading, intrinsicLoading,
  revenueGrowth, setRevenueGrowth,
  terminalGrowth, setTerminalGrowth,
  discountRate, setDiscountRate,
  marginImprovement, setMarginImprovement,
}: {
  dcfData: any; intrinsicData: any; dcfLoading: boolean; intrinsicLoading: boolean;
  revenueGrowth: number; setRevenueGrowth: (v: number) => void;
  terminalGrowth: number; setTerminalGrowth: (v: number) => void;
  discountRate: number; setDiscountRate: (v: number) => void;
  marginImprovement: number; setMarginImprovement: (v: number) => void;
}) {
  if (dcfLoading) {
    return <div className="mt-6"><Skeleton className="h-64 w-full" /></div>;
  }

  const fv = dcfData?.fair_value_with_cash;
  const upside = dcfData?.upside_pct;
  const verdict = dcfData?.verdict;
  const sensitivity = dcfData?.sensitivity;

  return (
    <div className="mt-6 space-y-6">
      {/* DCF Controls */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base flex items-center gap-2">
            <BarChart3 className="h-4 w-4" />
            DCF Valuation Model
          </CardTitle>
          <CardDescription>Adjust assumptions to see how fair value changes</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
            <Slider
              label="Revenue Growth (5yr)"
              value={revenueGrowth}
              min={-10}
              max={50}
              step={1}
              onValueChange={setRevenueGrowth}
              formatValue={(v) => `${v}%`}
            />
            <Slider
              label="Terminal Growth"
              value={terminalGrowth}
              min={0}
              max={6}
              step={0.5}
              onValueChange={setTerminalGrowth}
              formatValue={(v) => `${v}%`}
            />
            <Slider
              label="Discount Rate (WACC)"
              value={discountRate}
              min={5}
              max={20}
              step={0.5}
              onValueChange={setDiscountRate}
              formatValue={(v) => `${v}%`}
            />
            <Slider
              label="Margin Improvement"
              value={marginImprovement}
              min={-5}
              max={10}
              step={0.5}
              onValueChange={setMarginImprovement}
              formatValue={(v) => `${v}%`}
            />
          </div>
        </CardContent>
      </Card>

      {/* DCF Results */}
      {dcfData && (
        <>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <Card className="p-6">
              <p className="text-sm text-[#6b7f8e]">DCF Fair Value</p>
              <p className="text-3xl font-bold mt-1">
                {fv !== null && fv !== undefined ? formatPrice(fv) : "N/A"}
              </p>
              {upside !== null && upside !== undefined && (
                <p className={`text-sm mt-1 ${upside >= 0 ? "text-emerald-400" : "text-red-400"}`}>
                  {upside >= 0 ? "+" : ""}{upside.toFixed(1)}% upside
                </p>
              )}
            </Card>
            <Card className="p-6">
              <p className="text-sm text-[#6b7f8e]">Verdict</p>
              <p className={`text-xl font-bold mt-1 ${
                verdict?.includes("Undervalued") ? "text-emerald-400" :
                verdict?.includes("Overvalued") ? "text-red-400" : "text-yellow-400"
              }`}>
                {verdict ?? "N/A"}
              </p>
            </Card>
            <Card className="p-6">
              <p className="text-sm text-[#6b7f8e]">Enterprise Value</p>
              <p className="text-xl font-bold mt-1">
                {formatCurrency(dcfData.enterprise_value)}
              </p>
            </Card>
          </div>

          {/* DCF Projection Table */}
          <Card>
            <CardHeader>
              <CardTitle className="text-base">5-Year Projection</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-[#1e2d3a]">
                      <th className="text-left py-2 text-[#6b7f8e]">Year</th>
                      {[1, 2, 3, 4, 5].map((y) => (
                        <th key={y} className="text-right py-2 text-[#6b7f8e]">Year {y}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    <tr className="border-b border-[#1e2d3a]/50">
                      <td className="py-2 text-[#c8d8e4]">Revenue</td>
                      {dcfData.projected_revenue?.map((v: number, i: number) => (
                        <td key={i} className="text-right py-2 font-mono text-[#6b7f8e]">
                          {formatCurrency(v)}
                        </td>
                      ))}
                    </tr>
                    <tr className="border-b border-[#1e2d3a]/50">
                      <td className="py-2 text-[#c8d8e4]">Free Cash Flow</td>
                      {dcfData.projected_fcf?.map((v: number, i: number) => (
                        <td key={i} className="text-right py-2 font-mono text-[#6b7f8e]">
                          {formatCurrency(v)}
                        </td>
                      ))}
                    </tr>
                    <tr>
                      <td className="py-2 text-[#c8d8e4]">Present Value</td>
                      {dcfData.pv_fcf?.map((v: number, i: number) => (
                        <td key={i} className="text-right py-2 font-mono text-[#6b7f8e]">
                          {formatCurrency(v)}
                        </td>
                      ))}
                    </tr>
                  </tbody>
                </table>
              </div>
            </CardContent>
          </Card>

          {/* Sensitivity Heatmap */}
          {sensitivity && (
            <Card>
              <CardHeader>
                <CardTitle className="text-base">Sensitivity Analysis — Upside %</CardTitle>
                <CardDescription>How upside changes with different WACC and growth assumptions</CardDescription>
              </CardHeader>
              <CardContent>
                <div className="inline-block">
                  <table className="text-xs">
                    <thead>
                      <tr>
                        <th className="p-2 text-[#6b7f8e]">Growth \ WACC</th>
                        {sensitivity.wacc_range?.map((w: number, i: number) => (
                          <th key={i} className="p-2 text-[#6b7f8e] font-mono">{w.toFixed(1)}%</th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {sensitivity.growth_range?.map((g: number, rowI: number) => (
                        <tr key={rowI}>
                          <td className="p-2 text-[#6b7f8e] font-mono">{g.toFixed(1)}%</td>
                          {sensitivity.matrix?.[rowI]?.map((val: number | null, colI: number) => (
                            <td
                              key={colI}
                              className={`p-2 font-mono text-center rounded ${getSensitivityCellColor(val)}`}
                            >
                              {val !== null ? `${val >= 0 ? "+" : ""}${val.toFixed(1)}%` : "—"}
                            </td>
                          ))}
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </CardContent>
            </Card>
          )}

          {/* Intrinsic Worth Cards */}
          {intrinsicData && !intrinsicLoading && (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
              <IntrinsicCard
                title="Graham Fair Value"
                value={intrinsicData.breakdown?.graham_number}
                label={intrinsicData.breakdown?.graham_ratio !== null && intrinsicData.breakdown?.graham_ratio !== undefined
                  ? `${intrinsicData.breakdown.graham_ratio}x current price`
                  : undefined}
              />
              <IntrinsicCard
                title="FCF Yield"
                value={intrinsicData.breakdown?.fcf_yield}
                suffix="%"
                label="Cash return on investment"
              />
              <IntrinsicCard
                title="Earnings Power Value"
                value={intrinsicData.breakdown?.earnings_power_value}
                label={intrinsicData.breakdown?.epv_ratio !== null && intrinsicData.breakdown?.epv_ratio !== undefined
                  ? `${intrinsicData.breakdown.epv_ratio}x current price`
                  : undefined}
              />
              <IntrinsicCard
                title="P/B Ratio"
                value={intrinsicData.breakdown?.pb_ratio}
                label="Price vs book value"
              />
            </div>
          )}
        </>
      )}
    </div>
  );
}

function IntrinsicCard({ title, value, suffix, label }: { title: string; value: number | null | undefined; suffix?: string; label?: string }) {
  return (
    <Card className="p-4">
      <p className="text-xs text-[#6b7f8e]">{title}</p>
      <p className="text-xl font-bold mt-1">
        {value !== null && value !== undefined
          ? typeof value === "number" && value > 100 ? formatCurrency(value) : `${value}${suffix ?? ""}`
          : "N/A"}
      </p>
      {label && <p className="text-xs text-[#3a5570] mt-1">{label}</p>}
    </Card>
  );
}

// ─── Risk Tab ──────────────────────────────────────────────────

function RiskTab({ riskData, riskLoading }: { riskData: any; riskLoading: boolean }) {
  if (riskLoading) {
    return (
      <div className="mt-6"><Skeleton className="h-64 w-full" /></div>
    );
  }

  const score = riskData?.score ?? 50;
  const label = riskData?.label ?? "Medium";
  const summary = riskData?.summary ?? "";
  const factors = riskData?.factors ?? [];
  const redFlags = riskData?.red_flags ?? [];

  return (
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 mt-6">
      {/* Risk Score */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base flex items-center gap-2">
            <Shield className="h-4 w-4" />
            Risk Assessment
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex items-center gap-4 mb-4">
            <ScoreBadge score={score} size="lg" showBar />
            <div>
              <RiskBadge label={label} />
              <p className="text-sm text-[#6b7f8e] mt-2">{summary}</p>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Red Flags */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base flex items-center gap-2">
            <AlertTriangle className="h-4 w-4 text-red-400" />
            Red Flags
          </CardTitle>
        </CardHeader>
        <CardContent>
          {redFlags.length > 0 ? (
            <div className="space-y-3">
              {redFlags.map((flag: { severity: string; title: string; explanation: string }, i: number) => (
                <div key={i} className="flex items-start gap-3">
                  <span className={`mt-0.5 ${flag.severity === "danger" ? "text-red-400" : "text-yellow-400"}`}>
                    <AlertTriangle className="h-4 w-4" />
                  </span>
                  <div>
                    <p className="text-sm font-medium text-[#f0f4f0]">{flag.title}</p>
                    <p className="text-xs text-[#6b7f8e]">{flag.explanation}</p>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <p className="text-sm text-[#6b7f8e]">No red flags identified.</p>
          )}
        </CardContent>
      </Card>

      {/* Risk Factors Detail */}
      <Card className="lg:col-span-2">
        <CardHeader>
          <CardTitle className="text-base">Risk Breakdown</CardTitle>
        </CardHeader>
        <CardContent>
          {factors.length > 0 ? (
            <div className="space-y-3">
              {factors.map((factor: [string, string, string], i: number) => (
                <div key={i} className="flex items-start gap-3 pb-3 border-b border-[#1e2d3a] last:border-0">
                  <span className={`mt-0.5 ${
                    factor[0] === "safe" ? "text-emerald-400" :
                    factor[0] === "warning" ? "text-yellow-400" : "text-red-400"
                  }`}>
                    {factor[0] === "safe" ? "✓" : "⚠"}
                  </span>
                  <div className="flex-1">
                    <p className="text-sm font-medium text-[#f0f4f0]">{factor[1]}</p>
                    <p className="text-xs text-[#6b7f8e] mt-0.5">{factor[2]}</p>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <p className="text-sm text-[#6b7f8e]">No risk factor data available.</p>
          )}
        </CardContent>
      </Card>
    </div>
  );
}

