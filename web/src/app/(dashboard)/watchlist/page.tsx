"use client";

import { useState, useMemo } from "react";
import Link from "next/link";
import {
  useEnrichedWatchlist,
  useAddToWatchlist,
  useRemoveFromWatchlist,
  useUser,
} from "@/hooks/use-watchlist";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Table,
  TableHeader,
  TableBody,
  TableHead,
  TableRow,
  TableCell,
} from "@/components/ui/table";
import { PeerScatter } from "@/components/charts/PeerScatter";
import { SectorPie } from "@/components/charts/SectorPie";
import {
  ScoreBadge,
  VerdictBadge,
  RiskBadge,
} from "@/components/shared";
import {
  formatPrice,
  formatPct,
  getHealthColor,
  getHealthBg,
  getRiskColor,
  cn,
} from "@/lib/utils";
import {
  Plus,
  Trash2,
  ArrowUpDown,
  Search,
  ExternalLink,
  BarChart3,
  PieChart,
} from "lucide-react";

type SortKey = "ticker" | "price" | "change_pct" | "healthScore" | "growth3m" | "growth6m" | "growth12m";
type SortDir = "asc" | "desc";

export default function WatchlistPage() {
  const { data: userData } = useUser();
  const userId = userData?.id ?? 0;
  const { data: enrichedItems, isLoading: enrichedLoading } = useEnrichedWatchlist(userId);
  const addMutation = useAddToWatchlist(userId);
  const removeMutation = useRemoveFromWatchlist(userId);
  const [newTicker, setNewTicker] = useState("");
  const [sortKey, setSortKey] = useState<SortKey>("healthScore");
  const [sortDir, setSortDir] = useState<SortDir>("desc");
  const [searchFilter, setSearchFilter] = useState("");

  // Use enriched API data
  const items = useMemo(() => {
    if (enrichedLoading) return [];
    return (enrichedItems ?? []).filter((i) => !i.error);
  }, [enrichedItems, enrichedLoading]);

  // Filter and sort
  const filtered = useMemo(() => {
    let result = [...items];
    if (searchFilter) {
      const s = searchFilter.toLowerCase();
      result = result.filter(
        (i) =>
          i.ticker.toLowerCase().includes(s) ||
          i.name.toLowerCase().includes(s) ||
          i.sector.toLowerCase().includes(s)
      );
    }
    result.sort((a, b) => {
      const aVal = a[sortKey];
      const bVal = b[sortKey];
      const aN = aVal ?? -Infinity;
      const bN = bVal ?? -Infinity;
      if (typeof aN === "string" && typeof bN === "string") {
        return sortDir === "asc" ? aN.localeCompare(bN) : bN.localeCompare(aN);
      }
      return sortDir === "asc" ? (aN as number) - (bN as number) : (bN as number) - (aN as number);
    });
    return result;
  }, [items, searchFilter, sortKey, sortDir]);

  const handleSort = (key: SortKey) => {
    if (sortKey === key) {
      setSortDir((d) => (d === "asc" ? "desc" : "asc"));
    } else {
      setSortKey(key);
      setSortDir("desc");
    }
  };

  const handleAdd = () => {
    if (newTicker.trim()) {
      addMutation.mutate(newTicker.trim().toUpperCase());
      setNewTicker("");
    }
  };

  const handleRemove = (ticker: string) => {
    removeMutation.mutate(ticker);
  };

  // Sector breakdown
  const sectorData = useMemo(() => {
    const counts: Record<string, number> = {};
    items.forEach((i) => {
      counts[i.sector] = (counts[i.sector] || 0) + 1;
    });
    return Object.entries(counts).map(([name, count]) => ({ name, count }));
  }, [items]);

  // Peer scatter data
  const peerData = useMemo(() => {
    return items.map((i) => ({
      name: i.ticker,
      healthScore: i.healthScore,
      riskScore: i.riskLabel === "Low" ? 80 : i.riskLabel === "Medium" ? 50 : 20,
    }));
  }, [items]);

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold">Watchlist</h1>
        <p className="text-sm text-[#6b7f8e] mt-1">
          {enrichedLoading ? "Loading watchlist data..." : `${items.length} companies tracked • Click a row to view details`}
        </p>
      </div>

      {/* Add Ticker */}
      <Card>
        <CardContent className="pt-6">
          <form
            onSubmit={(e) => {
              e.preventDefault();
              handleAdd();
            }}
            className="flex gap-2"
          >
            <Input
              placeholder="Enter ticker symbol (e.g., AAPL)"
              value={newTicker}
              onChange={(e) => setNewTicker(e.target.value.toUpperCase())}
              className="max-w-xs"
            />
            <Button type="submit" disabled={addMutation.isPending || !newTicker.trim()}>
              <Plus className="h-4 w-4 mr-1" />
              Add
            </Button>
          </form>
        </CardContent>
      </Card>

      {/* Search */}
      <div className="relative w-72">
        <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-[#6b7f8e]" />
        <Input
          placeholder="Filter watchlist..."
          value={searchFilter}
          onChange={(e) => setSearchFilter(e.target.value)}
          className="pl-9"
        />
      </div>

      {/* Data Table */}
      <Card>
        <CardContent className="p-0">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead className="w-24">
                  <SortableHeader label="Ticker" sortKey="ticker" currentSort={sortKey} currentDir={sortDir} onClick={handleSort} />
                </TableHead>
                <TableHead className="w-28 text-right">Price</TableHead>
                <TableHead className="w-24 text-right">
                  <SortableHeader label="Change" sortKey="change_pct" currentSort={sortKey} currentDir={sortDir} onClick={handleSort} />
                </TableHead>
                <TableHead className="w-28">
                  <SortableHeader label="Health" sortKey="healthScore" currentSort={sortKey} currentDir={sortDir} onClick={handleSort} />
                </TableHead>
                <TableHead className="w-24">Verdict</TableHead>
                <TableHead className="w-24">Risk</TableHead>
                <TableHead className="w-20 text-right">
                  <SortableHeader label="3M" sortKey="growth3m" currentSort={sortKey} currentDir={sortDir} onClick={handleSort} />
                </TableHead>
                <TableHead className="w-20 text-right">
                  <SortableHeader label="6M" sortKey="growth6m" currentSort={sortKey} currentDir={sortDir} onClick={handleSort} />
                </TableHead>
                <TableHead className="w-20 text-right">
                  <SortableHeader label="12M" sortKey="growth12m" currentSort={sortKey} currentDir={sortDir} onClick={handleSort} />
                </TableHead>
                <TableHead className="w-16"></TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {enrichedLoading ? (
                Array.from({ length: 5 }).map((_, i) => (
                  <TableRow key={i}>
                    {[1, 2, 3, 4, 5, 6, 7, 8, 9].map((j) => (
                      <TableCell key={j}>
                        <Skeleton className="h-4 w-16" />
                      </TableCell>
                    ))}
                  </TableRow>
                ))
              ) : filtered.length === 0 ? (
                <TableRow>
                  <TableCell colSpan={10} className="text-center py-8 text-[#6b7f8e]">
                    No watchlist items found.
                  </TableCell>
                </TableRow>
              ) : (
                filtered.map((item) => (
                  <TableRow
                    key={item.ticker}
                    className="cursor-pointer"
                    onClick={() => (window.location.href = `/company/${item.ticker}`)}
                  >
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
                    <TableCell className={`text-right font-mono ${item.change_pct >= 0 ? "text-emerald-400" : "text-red-400"}`}>
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
                          handleRemove(item.ticker);
                        }}
                        className="h-7 w-7 text-zinc-500 hover:text-red-400"
                      >
                        <Trash2 className="h-3.5 w-3.5" />
                      </Button>
                    </TableCell>
                  </TableRow>
                ))
              )}
            </TableBody>
          </Table>
        </CardContent>
      </Card>

      {/* Charts */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <Card>
          <CardHeader>
            <CardTitle className="text-base flex items-center gap-2">
              <BarChart3 className="h-4 w-4" />
              Peer Comparison
            </CardTitle>
            <p className="text-xs text-[#6b7f8e]">Health Score vs Risk Score</p>
          </CardHeader>
          <CardContent>
            <PeerScatter data={peerData} />
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="text-base flex items-center gap-2">
              <PieChart className="h-4 w-4" />
              Sector Breakdown
            </CardTitle>
            <p className="text-xs text-[#6b7f8e]">Distribution across sectors</p>
          </CardHeader>
          <CardContent>
            <SectorPie data={sectorData} />
          </CardContent>
        </Card>
      </div>
    </div>
  );
}

function SortableHeader({ label, sortKey, currentSort, currentDir, onClick }: {
  label: string; sortKey: SortKey; currentSort: SortKey; currentDir: SortDir; onClick: (key: SortKey) => void;
}) {
  return (
    <button
      onClick={() => onClick(sortKey)}
      className="flex items-center gap-1 text-[#6b7f8e] hover:text-[#c8d8e4] transition-colors"
    >
      {label}
      <ArrowUpDown className={cn("h-3 w-3", currentSort === sortKey ? "text-[#84cc16]" : "text-[#3a5570]")} />
    </button>
  );
}

function GrowthCell({ value }: { value: number | null }) {
  if (value === null) return <TableCell className="text-right text-zinc-600">N/A</TableCell>;
  return (
    <TableCell className={`text-right font-mono ${value >= 0 ? "text-emerald-400" : "text-red-400"}`}>
      {formatPct(value)}
    </TableCell>
  );
}
