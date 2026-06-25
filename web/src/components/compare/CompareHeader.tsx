"use client";

import { useState, useEffect, useCallback } from "react";
import { useCompareStore } from "@/stores/compare-store";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";
import {
  DropdownMenu,
  DropdownMenuTrigger,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
} from "@/components/ui/dropdown-menu";
import { X, Plus, Trash2, History, ChevronDown } from "lucide-react";
import { api } from "@/lib/api-client";

const MAX_TICKERS = 10;

export function CompareHeader() {
  const {
    tickers,
    addTicker,
    removeTicker,
    clearAll,
    suggestedPeers,
    setSuggestedPeers,
    clearSuggestedPeers,
    setTickers,
    comparisonHistory,
    addComparison,
  } = useCompareStore();
  const [inputValue, setInputValue] = useState("");
  const [showPeers, setShowPeers] = useState(false);

  // Auto-fetch peers when first ticker is added
  const prevTickerCount = useCompareStore(
    useCallback((s) => s.tickers.length, [])
  );

  // Track prev ticker count outside of render
  const [prevCount, setPrevCount] = useState(0);

  useEffect(() => {
    if (tickers.length === 1 && prevCount === 0) {
      // First ticker added — fetch peers
      const ticker = tickers[0];
      api
        .get<{ peers: string[]; industry?: string }>(`/api/data/${ticker}/peers`)
        .then((data) => {
          const peers = (data.peers ?? [])
            .map((p: string) => p.toUpperCase().trim())
            .filter((p: string) => p && p !== ticker && !tickers.includes(p))
            .slice(0, 8);
          if (peers.length > 0) {
            setSuggestedPeers(peers);
            setShowPeers(true);
          }
        })
        .catch(() => {
          // Silently fail — peers are optional
        });
    }
    setPrevCount(tickers.length);
  }, [tickers.length]); // eslint-disable-line react-hooks/exhaustive-deps

  // Save comparison to history whenever we have >= 2 tickers
  useEffect(() => {
    if (tickers.length >= 2) {
      addComparison(tickers);
    }
  }, [tickers.join(",")]); // eslint-disable-line react-hooks/exhaustive-deps

  const handleAdd = () => {
    const val = inputValue.trim().toUpperCase();
    if (val && tickers.length < MAX_TICKERS && !tickers.includes(val)) {
      addTicker(val);
      setInputValue("");
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter") {
      e.preventDefault();
      handleAdd();
    }
  };

  const handleRestoreHistory = (entry: { tickers: string[] }) => {
    setTickers(entry.tickers);
    clearSuggestedPeers();
    setShowPeers(false);
  };

  const handleAddPeer = (peer: string) => {
    addTicker(peer);
    if (tickers.length + 1 >= 2) {
      // Remove from suggested peers
      setSuggestedPeers(suggestedPeers.filter((p) => p !== peer));
    }
  };

  const handleAddAllPeers = () => {
    suggestedPeers.forEach((peer) => addTicker(peer));
    clearSuggestedPeers();
    setShowPeers(false);
  };

  return (
    <div className="space-y-3">
      <Card>
        <CardContent className="pt-6">
          <div className="flex flex-wrap items-center gap-3">
            {/* Add ticker input */}
            <div className="flex items-center gap-2">
              <Input
                placeholder="Add ticker (e.g., AAPL)"
                value={inputValue}
                onChange={(e) => setInputValue(e.target.value.toUpperCase())}
                onKeyDown={handleKeyDown}
                className="w-40"
              />
              <Button
                variant="outline"
                size="icon"
                onClick={handleAdd}
                disabled={
                  !inputValue.trim() ||
                  tickers.length >= MAX_TICKERS ||
                  tickers.includes(inputValue.trim().toUpperCase())
                }
              >
                <Plus className="h-4 w-4" />
              </Button>
            </div>

            {/* Recent comparisons dropdown */}
            {comparisonHistory.length > 0 && (
              <DropdownMenu>
                <DropdownMenuTrigger asChild>
                  <Button variant="outline" size="sm" className="gap-1 text-xs">
                    <History className="h-3.5 w-3.5" />
                    Recent
                    <ChevronDown className="h-3 w-3" />
                  </Button>
                </DropdownMenuTrigger>
                <DropdownMenuContent align="start" className="w-56">
                  <DropdownMenuLabel className="text-xs text-[#6b7f8e]">
                    Recent Comparisons
                  </DropdownMenuLabel>
                  <DropdownMenuSeparator />
                  {comparisonHistory.map((entry, i) => (
                    <DropdownMenuItem
                      key={`${entry.timestamp}-${i}`}
                      onClick={() => handleRestoreHistory(entry)}
                      className="text-sm"
                    >
                      <span className="text-[#84cc16] font-medium">
                        {entry.tickers.join(", ")}
                      </span>
                      <span className="ml-auto text-xs text-[#6b7f8e]">
                        {new Date(entry.timestamp).toLocaleDateString()}
                      </span>
                    </DropdownMenuItem>
                  ))}
                </DropdownMenuContent>
              </DropdownMenu>
            )}

            {/* Ticker badges */}
            <div className="flex flex-wrap items-center gap-2">
              {tickers.map((ticker) => (
                <Badge
                  key={ticker}
                  variant="outline"
                  className="flex items-center gap-1.5 px-3 py-1.5 text-sm border-[#1e2d3a] bg-[#1a2a38]/50"
                >
                  <span className="text-[#84cc16] font-semibold">{ticker}</span>
                  <button
                    onClick={() => removeTicker(ticker)}
                    className="text-[#6b7f8e] hover:text-red-400 transition-colors"
                  >
                    <X className="h-3 w-3" />
                  </button>
                </Badge>
              ))}
            </div>

            {/* Clear all */}
            {tickers.length > 0 && (
              <Button
                variant="ghost"
                size="sm"
                onClick={() => {
                  clearAll();
                  clearSuggestedPeers();
                  setShowPeers(false);
                }}
                className="text-[#6b7f8e] hover:text-red-400"
              >
                <Trash2 className="h-3.5 w-3.5 mr-1" />
                Clear All
              </Button>
            )}

            {/* Max count indicator */}
            <span className="text-xs text-[#6b7f8e] ml-auto">
              {tickers.length}/{MAX_TICKERS}
            </span>
          </div>
        </CardContent>
      </Card>

      {/* Suggested peers drawer */}
      {showPeers && suggestedPeers.length > 0 && (
        <Card className="border-[#1e2d3a] bg-[#111922]/80">
          <CardContent className="py-3">
            <div className="flex items-center justify-between mb-2">
              <span className="text-xs text-[#6b7f8e] font-medium">
                Suggested peers from sector
              </span>
              <div className="flex items-center gap-2">
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={handleAddAllPeers}
                  className="text-xs h-6 text-[#84cc16] hover:text-[#65a30d]"
                >
                  Add All
                </Button>
                <button
                  onClick={() => setShowPeers(false)}
                  className="text-[#6b7f8e] hover:text-[#c8d8e4] transition-colors"
                >
                  <X className="h-3.5 w-3.5" />
                </button>
              </div>
            </div>
            <div className="flex flex-wrap gap-2">
              {suggestedPeers.map((peer) => (
                <Badge
                  key={peer}
                  variant="outline"
                  className="flex items-center gap-1 px-2.5 py-1 text-xs border-[#1e2d3a] bg-[#1a2a38]/30 cursor-pointer hover:border-[#84cc16]/30 hover:bg-[#1a2a38]/60 transition-colors"
                  onClick={() => handleAddPeer(peer)}
                >
                  <Plus className="h-2.5 w-2.5 text-[#84cc16]" />
                  {peer}
                </Badge>
              ))}
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
