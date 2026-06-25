"use client";

import { useState, useMemo } from "react";
import {
  useEnrichedWatchlist,
  useAddToWatchlist,
  useRemoveFromWatchlist,
  useUser,
} from "@/hooks/use-watchlist";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { WatchlistTable } from "@/components/watchlist/WatchlistTable";
import { PeerScatter } from "@/components/charts/PeerScatter";
import { SectorPie } from "@/components/charts/SectorPie";
import {
  Plus,
  Search,
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
          <WatchlistTable
            items={filtered}
            isLoading={enrichedLoading}
            onRemove={handleRemove}
          />
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
