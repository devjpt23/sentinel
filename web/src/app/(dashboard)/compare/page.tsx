"use client";

import { useEffect, useMemo } from "react";
import { useSearchParams } from "next/navigation";
import { useCompareStore } from "@/stores/compare-store";
import { useCompare } from "@/hooks/use-compare";
import { CompareHeader } from "@/components/compare/CompareHeader";
import { ComparePriceOverlay } from "@/components/compare/ComparePriceOverlay";
import { CompareTable } from "@/components/compare/CompareTable";
import { LoadingSpinner } from "@/components/shared/loading-spinner";
import { Card, CardContent } from "@/components/ui/card";
import { AlertTriangle, BarChart3 } from "lucide-react";

export default function ComparePage() {
  const searchParams = useSearchParams();
  const tickers = useCompareStore((s) => s.tickers);
  const setTickers = useCompareStore((s) => s.setTickers);

  // Initialize from URL params on mount
  useEffect(() => {
    const urlTickers = searchParams.get("tickers");
    if (urlTickers) {
      const parsed = urlTickers
        .split(",")
        .map((t) => t.trim().toUpperCase())
        .filter((t) => t.length > 0);
      if (parsed.length > 0) {
        setTickers(parsed);
      }
    }
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const { data: items, isLoading, error } = useCompare(tickers);

  const validItems = useMemo(() => items ?? [], [items]);

  // Clear state
  const hasTickers = tickers.length > 0;
  const enoughTickers = tickers.length >= 2;

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold">Compare Stocks</h1>
        <p className="text-sm text-[#6b7f8e] mt-1">
          Side-by-side comparison across valuation, health, risk, and growth metrics
        </p>
      </div>

      <CompareHeader />

      {/* Loading state */}
      {isLoading && (
        <Card>
          <CardContent className="py-12">
            <LoadingSpinner size="md" text="Fetching comparison data..." />
          </CardContent>
        </Card>
      )}

      {/* Error state */}
      {error && !isLoading && (
        <Card>
          <CardContent className="py-8">
            <div className="flex flex-col items-center gap-3 text-center">
              <AlertTriangle className="h-8 w-8 text-red-400" />
              <p className="text-sm text-red-400 font-medium">Failed to load comparison data</p>
              <p className="text-xs text-[#6b7f8e] max-w-md">
                {(error as Error)?.message || "An unexpected error occurred. Check your backend connection."}
              </p>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Empty state — prompt to add tickers */}
      {!isLoading && !error && hasTickers && !enoughTickers && (
        <Card>
          <CardContent className="py-12">
            <div className="flex flex-col items-center gap-3 text-center">
              <BarChart3 className="h-10 w-10 text-[#3a5570]" />
              <p className="text-sm text-[#6b7f8e]">Add at least 2 tickers to compare</p>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Empty state — no tickers */}
      {!isLoading && !error && !hasTickers && (
        <Card>
          <CardContent className="py-12">
            <div className="flex flex-col items-center gap-3 text-center">
              <BarChart3 className="h-10 w-10 text-[#3a5570]" />
              <p className="text-sm text-[#6b7f8e]">
                Enter ticker symbols above to compare stocks side-by-side
              </p>
              <p className="text-xs text-[#4a6070]">
                Try: AAPL, MSFT, NVDA, GOOGL, AMZN
              </p>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Results */}
      {!isLoading && !error && enoughTickers && validItems.length > 0 && (
        <div className="space-y-6">
          <ComparePriceOverlay items={validItems} isLoading={false} />
          <CompareTable items={validItems} isLoading={false} />
        </div>
      )}

      {/* Partial results (some tickers failed) */}
      {!isLoading && !error && enoughTickers && items && validItems.length < tickers.length && validItems.length > 0 && (
        <div className="rounded-lg border border-yellow-500/30 bg-yellow-500/10 p-3">
          <p className="text-xs text-yellow-400">
            Some tickers failed to load. Showing data for {validItems.length} of {tickers.length} tickers.
          </p>
        </div>
      )}
    </div>
  );
}
