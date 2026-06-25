"use client";

import { useState } from "react";
import { useCompareStore } from "@/stores/compare-store";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";
import { X, Plus, Trash2 } from "lucide-react";

const MAX_TICKERS = 10;

export function CompareHeader() {
  const { tickers, addTicker, removeTicker, clearAll } = useCompareStore();
  const [inputValue, setInputValue] = useState("");

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

  return (
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
              onClick={clearAll}
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
  );
}
