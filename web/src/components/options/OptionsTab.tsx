"use client";

import { useOptions } from "@/hooks/use-company-data";
import { OptionsSummaryPanel } from "./OptionsSummaryPanel";
import { OptionsChainTable } from "./OptionsChainTable";
import { Card, CardContent } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";

interface OptionsTabProps {
  ticker: string;
}

export function OptionsTab({ ticker }: OptionsTabProps) {
  const { data: optionsData, isLoading, error } = useOptions(ticker);

  const data = optionsData as {
    ticker?: string;
    underlying_price?: number;
    summary?: {
      atm_iv?: number;
      put_call_ratio_oi?: number;
      put_call_ratio_vol?: number;
      max_pain?: number;
      total_call_oi?: number;
      total_put_oi?: number;
    };
    expirations?: string[];
    chain?: Record<string, { calls: unknown[]; puts: unknown[] }>;
  } | undefined;

  // ── Error state ───────────────────────────────────────────────
  if (error) {
    return (
      <div className="mt-6">
        <Card className="border-red-500/30 bg-red-500/5">
          <CardContent className="p-6">
            <p className="text-sm font-semibold text-red-400">
              Failed to load options data
            </p>
            <p className="text-xs text-[#6b7f8e] mt-1">
              {(error as Error)?.message ||
                "An error occurred while fetching options data."}
            </p>
          </CardContent>
        </Card>
      </div>
    );
  }

  // ── Loading state ─────────────────────────────────────────────
  if (isLoading) {
    return (
      <div className="mt-6 space-y-4">
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
          {Array.from({ length: 4 }).map((_, i) => (
            <Card key={i} className="p-4 bg-[#15202b] border-[#1e2d3a]">
              <Skeleton className="h-4 w-16 mb-2" />
              <Skeleton className="h-8 w-24" />
            </Card>
          ))}
        </div>
        <Card className="p-4 bg-[#15202b] border-[#1e2d3a]">
          <div className="flex gap-2 mb-4">
            {Array.from({ length: 4 }).map((_, i) => (
              <Skeleton key={i} className="h-8 w-20" />
            ))}
          </div>
          {Array.from({ length: 8 }).map((_, i) => (
            <Skeleton key={i} className="h-10 w-full mb-2" />
          ))}
        </Card>
      </div>
    );
  }

  // ── Empty / no-data state ─────────────────────────────────────
  if (
    !data ||
    !data.expirations ||
    data.expirations.length === 0 ||
    !data.chain ||
    Object.keys(data.chain).length === 0
  ) {
    return (
      <div className="mt-6">
        <Card className="p-8 bg-[#15202b] border-[#1e2d3a]">
          <p className="text-center text-[#6b7f8e]">No options data available</p>
        </Card>
      </div>
    );
  }

  // ── Success state ─────────────────────────────────────────────
  const summary = data.summary
    ? {
        atm_iv: data.summary.atm_iv ?? null,
        put_call_ratio_oi: data.summary.put_call_ratio_oi ?? null,
        put_call_ratio_vol: data.summary.put_call_ratio_vol ?? null,
        max_pain: data.summary.max_pain ?? null,
        total_call_oi: data.summary.total_call_oi ?? null,
        total_put_oi: data.summary.total_put_oi ?? null,
      }
    : null;

  const underlyingPrice = data.underlying_price ?? null;

  // Map raw API chain data to typed contract objects
  const chain: Record<string, { calls: import("./OptionsChainTable").OptionContract[]; puts: import("./OptionsChainTable").OptionContract[] }> | null =
    data.chain
      ? Object.fromEntries(
          Object.entries(data.chain).map(([expiry, chainData]) => [
            expiry,
            {
              calls: ((chainData.calls ?? []) as Record<string, unknown>[]).map((c) => ({
                strike: Number(c.strike),
                contract_id: String(c.contract_id ?? ""),
                last_price: (c.last_price as number) ?? null,
                bid: (c.bid as number) ?? null,
                ask: (c.ask as number) ?? null,
                volume: (c.volume as number) ?? null,
                open_interest: (c.open_interest as number) ?? null,
                iv: (c.iv as number) ?? null,
                delta: (c.delta as number) ?? null,
                gamma: (c.gamma as number) ?? null,
                theta: (c.theta as number) ?? null,
                vega: (c.vega as number) ?? null,
                rho: (c.rho as number) ?? null,
              })),
              puts: ((chainData.puts ?? []) as Record<string, unknown>[]).map((p) => ({
                strike: Number(p.strike),
                contract_id: String(p.contract_id ?? ""),
                last_price: (p.last_price as number) ?? null,
                bid: (p.bid as number) ?? null,
                ask: (p.ask as number) ?? null,
                volume: (p.volume as number) ?? null,
                open_interest: (p.open_interest as number) ?? null,
                iv: (p.iv as number) ?? null,
                delta: (p.delta as number) ?? null,
                gamma: (p.gamma as number) ?? null,
                theta: (p.theta as number) ?? null,
                vega: (p.vega as number) ?? null,
                rho: (p.rho as number) ?? null,
              })),
            },
          ]),
        )
      : null;

  return (
    <div className="mt-6 space-y-4">
      <OptionsSummaryPanel
        summary={summary}
        underlyingPrice={underlyingPrice}
        isLoading={false}
      />
      <OptionsChainTable
        chain={chain}
        expirations={data.expirations}
        underlyingPrice={underlyingPrice}
        isLoading={false}
      />
    </div>
  );
}
