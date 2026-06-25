"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useWatchlistStore } from "@/stores/watchlist-store";
import { Checkbox } from "@/components/ui/checkbox";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Table,
  TableHeader,
  TableBody,
  TableHead,
  TableRow,
  TableCell,
} from "@/components/ui/table";
import { ScoreBadge, VerdictBadge, RiskBadge } from "@/components/shared";
import { formatPrice, formatPct } from "@/lib/utils";
import { ExternalLink, Trash2, BarChart3 } from "lucide-react";
import type { EnrichedWatchlistItem } from "@/hooks/use-watchlist";

interface WatchlistTableProps {
  items: EnrichedWatchlistItem[];
  isLoading: boolean;
  onRemove: (ticker: string) => void;
}

export function WatchlistTable({
  items,
  isLoading,
  onRemove,
}: WatchlistTableProps) {
  const router = useRouter();
  const selectedForCompare = useWatchlistStore((s) => s.selectedForCompare);
  const toggleCompareSelection = useWatchlistStore(
    (s) => s.toggleCompareSelection
  );
  const clearCompareSelection = useWatchlistStore(
    (s) => s.clearCompareSelection
  );

  const handleCompareSelected = () => {
    const tickers = selectedForCompare.join(",");
    clearCompareSelection();
    router.push(`/compare?tickers=${tickers}`);
  };

  if (isLoading) {
    return (
      <div className="space-y-2 p-4">
        {Array.from({ length: 5 }).map((_, i) => (
          <Skeleton key={i} className="h-8 w-full" />
        ))}
      </div>
    );
  }

  if (items.length === 0) {
    return (
      <div className="text-center py-8 text-[#6b7f8e]">
        No watchlist items found.
      </div>
    );
  }

  return (
    <div>
      {/* Compare Selected button */}
      {selectedForCompare.length >= 2 && (
        <div className="mb-3">
          <Button
            size="sm"
            onClick={handleCompareSelected}
            className="gap-1.5 text-xs"
          >
            <BarChart3 className="h-3.5 w-3.5" />
            Compare Selected ({selectedForCompare.length})
          </Button>
        </div>
      )}

      <Table>
        <TableHeader>
          <TableRow>
            <TableHead className="w-10">
              <span className="sr-only">Select</span>
            </TableHead>
            <TableHead className="w-24">Ticker</TableHead>
            <TableHead className="w-28 text-right">Price</TableHead>
            <TableHead className="w-24 text-right">Change</TableHead>
            <TableHead className="w-28">Health</TableHead>
            <TableHead className="w-24">Verdict</TableHead>
            <TableHead className="w-24">Risk</TableHead>
            <TableHead className="w-20 text-right">3M</TableHead>
            <TableHead className="w-20 text-right">6M</TableHead>
            <TableHead className="w-20 text-right">12M</TableHead>
            <TableHead className="w-16"></TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {items.map((item) => {
            const isSelected = selectedForCompare.includes(item.ticker);
            return (
              <TableRow
                key={item.ticker}
                className="cursor-pointer"
                onClick={() =>
                  (window.location.href = `/company/${item.ticker}`)
                }
              >
                {/* Checkbox column */}
                <TableCell onClick={(e) => e.stopPropagation()}>
                  <Checkbox
                    checked={isSelected}
                    onCheckedChange={() =>
                      toggleCompareSelection(item.ticker)
                    }
                    aria-label={`Select ${item.ticker} for comparison`}
                  />
                </TableCell>
                <TableCell className="font-semibold">
                  <Link
                    href={`/company/${item.ticker}`}
                    className="flex items-center gap-1 text-[#84cc16] hover:text-[#65a30d] transition-colors"
                    onClick={(e) => e.stopPropagation()}
                  >
                    {item.ticker}
                    <ExternalLink className="h-3 w-3" />
                  </Link>
                </TableCell>
                <TableCell className="text-right font-mono">
                  {formatPrice(item.price)}
                </TableCell>
                <TableCell
                  className={`text-right font-mono ${
                    item.change_pct >= 0
                      ? "text-emerald-400"
                      : "text-red-400"
                  }`}
                >
                  {formatPct(item.change_pct)}
                </TableCell>
                <TableCell>
                  <ScoreBadge score={item.healthScore} size="sm" />
                </TableCell>
                <TableCell>
                  <VerdictBadge verdict={item.verdict} />
                </TableCell>
                <TableCell>
                  <RiskBadge label={item.riskLabel} />
                </TableCell>
                <GrowthCell value={item.growth3m} />
                <GrowthCell value={item.growth6m} />
                <GrowthCell value={item.growth12m} />
                <TableCell>
                  <Button
                    variant="ghost"
                    size="icon"
                    onClick={(e) => {
                      e.stopPropagation();
                      onRemove(item.ticker);
                    }}
                    className="h-7 w-7 text-zinc-500 hover:text-red-400"
                  >
                    <Trash2 className="h-3.5 w-3.5" />
                  </Button>
                </TableCell>
              </TableRow>
            );
          })}
        </TableBody>
      </Table>
    </div>
  );
}

function GrowthCell({ value }: { value: number | null }) {
  if (value === null)
    return <TableCell className="text-right text-zinc-600">N/A</TableCell>;
  return (
    <TableCell
      className={`text-right font-mono ${
        value >= 0 ? "text-emerald-400" : "text-red-400"
      }`}
    >
      {formatPct(value)}
    </TableCell>
  );
}
