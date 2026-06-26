"use client";

import { useState, useMemo, useEffect } from "react";
import { Card } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { formatCurrency, formatPercent, formatNumber } from "@/lib/utils";

export interface OptionContract {
  strike: number;
  contract_id: string;
  last_price: number | null;
  bid: number | null;
  ask: number | null;
  volume: number | null;
  open_interest: number | null;
  iv: number | null;
  delta: number | null;
  gamma: number | null;
  theta: number | null;
  vega: number | null;
  rho: number | null;
}

interface ChainForExpiry {
  calls: OptionContract[];
  puts: OptionContract[];
}

interface OptionsChainTableProps {
  chain: Record<string, ChainForExpiry> | null;
  expirations: string[];
  underlyingPrice: number | null;
  isLoading: boolean;
}

function findAtmStrike(rows: { strike: number }[], underlyingPrice: number | null): number | null {
  if (underlyingPrice === null || rows.length === 0) return null;
  return rows.reduce((closest, row) => {
    const currentDiff = Math.abs(row.strike - underlyingPrice);
    const closestDiff = Math.abs(closest - underlyingPrice);
    return currentDiff < closestDiff ? row.strike : closest;
  }, rows[0].strike);
}

export function OptionsChainTable({ chain, expirations, underlyingPrice, isLoading }: OptionsChainTableProps) {
  const [selectedExpiry, setSelectedExpiry] = useState<string>("");
  const [sortKey, setSortKey] = useState("strike");
  const [sortDir, setSortDir] = useState<"asc" | "desc">("asc");

  // Sync selected expiry with available expirations
  useEffect(() => {
    if (expirations.length > 0 && !expirations.includes(selectedExpiry)) {
      setSelectedExpiry(expirations[0]);
    }
  }, [expirations, selectedExpiry]);

  // Merge calls and puts into rows by strike
  const rows = useMemo(() => {
    if (!chain || !selectedExpiry || !chain[selectedExpiry]) return [];

    const { calls, puts } = chain[selectedExpiry];
    const strikeSet = new Set<number>();
    calls.forEach((c) => strikeSet.add(c.strike));
    puts.forEach((p) => strikeSet.add(p.strike));

    return Array.from(strikeSet)
      .sort((a, b) => a - b)
      .map((strike) => ({
        strike,
        call: calls.find((c) => c.strike === strike),
        put: puts.find((p) => p.strike === strike),
      }));
  }, [chain, selectedExpiry]);

  // Sort rows
  const sortedRows = useMemo(() => {
    const sorted = [...rows];
    sorted.sort((a, b) => {
      const getVal = (): [number | null, number | null] => {
        switch (sortKey) {
          case "strike":
            return [a.strike, b.strike];
          case "calls_ltp":
            return [a.call?.last_price ?? null, b.call?.last_price ?? null];
          case "calls_vol":
            return [a.call?.volume ?? null, b.call?.volume ?? null];
          case "calls_oi":
            return [a.call?.open_interest ?? null, b.call?.open_interest ?? null];
          case "calls_iv":
            return [a.call?.iv ?? null, b.call?.iv ?? null];
          case "puts_ltp":
            return [a.put?.last_price ?? null, b.put?.last_price ?? null];
          case "puts_vol":
            return [a.put?.volume ?? null, b.put?.volume ?? null];
          case "puts_oi":
            return [a.put?.open_interest ?? null, b.put?.open_interest ?? null];
          case "puts_iv":
            return [a.put?.iv ?? null, b.put?.iv ?? null];
          default:
            return [a.strike, b.strike];
        }
      };

      const [aVal, bVal] = getVal();

      if (aVal === null && bVal === null) return 0;
      if (aVal === null) return 1;
      if (bVal === null) return -1;

      return sortDir === "asc" ? aVal - bVal : bVal - aVal;
    });
    return sorted;
  }, [rows, sortKey, sortDir]);

  // Find ATM strike
  const atmStrike = useMemo(() => findAtmStrike(rows, underlyingPrice), [rows, underlyingPrice]);

  const handleSort = (key: string) => {
    if (sortKey === key) {
      setSortDir((d) => (d === "asc" ? "desc" : "asc"));
    } else {
      setSortKey(key);
      setSortDir("asc");
    }
  };

  const SortIndicator = ({ columnKey }: { columnKey: string }) => {
    if (sortKey !== columnKey) return null;
    return (
      <span className="ml-0.5 text-[10px]">
        {sortDir === "asc" ? "▲" : "▼"}
      </span>
    );
  };

  const renderCell = (value: number | null | undefined, formatter: (v: number) => string) => {
    if (isLoading) return <Skeleton className="h-4 w-14 inline-block" />;
    if (value === null || value === undefined)
      return <span className="text-[#3a5570]">—</span>;
    return formatter(value);
  };

  // ── Full loading state ─────────────────────────────────────────
  if (isLoading && expirations.length === 0) {
    return (
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
    );
  }

  // ── Empty state ────────────────────────────────────────────────
  if (!chain || Object.keys(chain).length === 0) {
    return (
      <Card className="p-8 bg-[#15202b] border-[#1e2d3a]">
        <p className="text-center text-[#6b7f8e]">No options data available</p>
      </Card>
    );
  }

  // ── Full table ─────────────────────────────────────────────────
  const columns = [
    { key: "calls_ltp", label: "LTP", side: "calls" as const },
    { key: "calls_vol", label: "Vol", side: "calls" as const },
    { key: "calls_oi", label: "OI", side: "calls" as const },
    { key: "calls_iv", label: "IV", side: "calls" as const },
  ] as const;

  const putColumns = [
    { key: "puts_ltp", label: "LTP", side: "puts" as const },
    { key: "puts_vol", label: "Vol", side: "puts" as const },
    { key: "puts_oi", label: "OI", side: "puts" as const },
    { key: "puts_iv", label: "IV", side: "puts" as const },
  ] as const;

  return (
    <Card className="bg-[#15202b] border-[#1e2d3a]">
      {/* Expiry Selector */}
      <div className="flex gap-2 p-4 pb-0 overflow-x-auto">
        {expirations.map((expiry) => (
          <button
            key={expiry}
            onClick={() => setSelectedExpiry(expiry)}
            className={`px-3 py-1.5 text-xs rounded-md transition-colors whitespace-nowrap ${
              expiry === selectedExpiry
                ? "bg-[#2a3f52] text-white font-medium"
                : "text-[#6b7f8e] hover:text-white hover:bg-[#1e2d3a]"
            }`}
          >
            {expiry}
          </button>
        ))}
      </div>

      {/* Chain Table */}
      <div className="overflow-x-auto p-4">
        <table className="w-full text-sm">
          <thead>
            {/* Group header row */}
            <tr className="border-b border-[#1e2d3a]">
              <th
                colSpan={4}
                className="text-right py-1.5 text-xs text-[#6b7f8e] font-normal uppercase tracking-wider"
              >
                Calls
              </th>
              <th className="text-center py-1.5 px-3 text-xs text-[#6b7f8e] font-normal uppercase tracking-wider">
                Strike
              </th>
              <th
                colSpan={4}
                className="text-left py-1.5 text-xs text-[#6b7f8e] font-normal uppercase tracking-wider"
              >
                Puts
              </th>
            </tr>
            {/* Column header row */}
            <tr className="border-b border-[#1e2d3a]">
              {columns.map((col) => (
                <th
                  key={col.key}
                  className="text-right py-1.5 px-1 cursor-pointer text-[#6b7f8e] hover:text-[#c8d8e4] transition-colors select-none"
                  onClick={() => handleSort(col.key)}
                >
                  <span className="inline-flex items-center text-xs font-normal">
                    {col.label}
                    <SortIndicator columnKey={col.key} />
                  </span>
                </th>
              ))}
              <th
                className="text-center py-1.5 px-3 cursor-pointer text-[#6b7f8e] hover:text-[#c8d8e4] transition-colors select-none"
                onClick={() => handleSort("strike")}
              >
                <span className="inline-flex items-center text-xs font-medium">
                  Strike
                  <SortIndicator columnKey="strike" />
                </span>
              </th>
              {putColumns.map((col) => (
                <th
                  key={col.key}
                  className="text-left py-1.5 px-1 cursor-pointer text-[#6b7f8e] hover:text-[#c8d8e4] transition-colors select-none"
                  onClick={() => handleSort(col.key)}
                >
                  <span className="inline-flex items-center text-xs font-normal">
                    <SortIndicator columnKey={col.key} />
                    {col.label}
                  </span>
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {sortedRows.length === 0 ? (
              <tr>
                <td colSpan={9} className="text-center py-8 text-[#6b7f8e] text-sm">
                  No options data available
                </td>
              </tr>
            ) : (
              sortedRows.map((row) => {
                const isAtm = row.strike === atmStrike;
                return (
                  <tr
                    key={row.strike}
                    className={`border-b border-[#1e2d3a]/50 last:border-0 transition-colors ${
                      isAtm ? "bg-[#84cc16]/10" : "hover:bg-[#1a2a38]"
                    }`}
                  >
                    {/* Calls side - right aligned */}
                    <td className="text-right py-2 px-1 font-mono text-xs text-[#c8d8e4]">
                      {renderCell(row.call?.last_price, formatCurrency)}
                    </td>
                    <td className="text-right py-2 px-1 font-mono text-xs text-[#c8d8e4]">
                      {renderCell(row.call?.volume, formatNumber)}
                    </td>
                    <td className="text-right py-2 px-1 font-mono text-xs text-[#c8d8e4]">
                      {renderCell(row.call?.open_interest, formatNumber)}
                    </td>
                    <td className="text-right py-2 px-1 font-mono text-xs text-[#c8d8e4]">
                      {renderCell(row.call?.iv, (v) => formatPercent(v, 1))}
                    </td>

                    {/* Strike - center */}
                    <td
                      className={`text-center py-2 px-3 text-xs font-bold ${
                        isAtm ? "text-[#84cc16]" : "text-[#c8d8e4]"
                      }`}
                    >
                      {row.strike}
                    </td>

                    {/* Puts side - left aligned */}
                    <td className="text-left py-2 px-1 font-mono text-xs text-[#c8d8e4]">
                      {renderCell(row.put?.last_price, formatCurrency)}
                    </td>
                    <td className="text-left py-2 px-1 font-mono text-xs text-[#c8d8e4]">
                      {renderCell(row.put?.volume, formatNumber)}
                    </td>
                    <td className="text-left py-2 px-1 font-mono text-xs text-[#c8d8e4]">
                      {renderCell(row.put?.open_interest, formatNumber)}
                    </td>
                    <td className="text-left py-2 px-1 font-mono text-xs text-[#c8d8e4]">
                      {renderCell(row.put?.iv, (v) => formatPercent(v, 1))}
                    </td>
                  </tr>
                );
              })
            )}
          </tbody>
        </table>
      </div>
    </Card>
  );
}
