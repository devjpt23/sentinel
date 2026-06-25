"use client";

import type { CompareItem } from "@/types/api";

interface ReturnsHeatmapProps {
  items: CompareItem[];
}

interface MonthlyReturn {
  label: string;
  monthKey: string; // "YYYY-MM"
  returnPct: number | null;
}

const MONTH_LABELS = [
  "Jan", "Feb", "Mar", "Apr", "May", "Jun",
  "Jul", "Aug", "Sep", "Oct", "Nov", "Dec",
];

/**
 * Derive monthly returns from price_history for each item.
 * Monthly return = (last price - first price) / first price * 100
 */
function computeMonthlyReturns(item: CompareItem): MonthlyReturn[] {
  const history = item.price_history;
  if (!history || history.length < 2) return [];

  // Group prices by month
  const monthGroups = new Map<string, number[]>();
  for (const entry of history) {
    const date = new Date(entry.date);
    if (isNaN(date.getTime())) continue;
    const monthKey = `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, "0")}`;
    if (!monthGroups.has(monthKey)) {
      monthGroups.set(monthKey, []);
    }
    monthGroups.get(monthKey)!.push(entry.price);
  }

  // Get last 12 months
  const sortedMonths = Array.from(monthGroups.keys()).sort();
  const last12 = sortedMonths.slice(-12);

  return last12.map((monthKey) => {
    const prices = monthGroups.get(monthKey)!;
    if (prices.length < 2) {
      return { label: monthKey, monthKey, returnPct: null };
    }
    const first = prices[0];
    const last = prices[prices.length - 1];
    const returnPct = ((last - first) / first) * 100;
    const monthNum = parseInt(monthKey.split("-")[1], 10) - 1;
    return {
      label: MONTH_LABELS[monthNum] || monthKey,
      monthKey,
      returnPct,
    };
  });
}

function getCellStyle(returnPct: number | null): React.CSSProperties {
  if (returnPct === null) {
    return { backgroundColor: "#1a1a2e", opacity: 1 };
  }
  const absReturn = Math.abs(returnPct);
  const opacity = Math.min(absReturn / 20, 1);
  if (returnPct >= 0) {
    return {
      backgroundColor: `rgba(34, 197, 94, ${opacity})`,
      color: opacity > 0.5 ? "#fff" : "#4ade80",
    };
  } else {
    return {
      backgroundColor: `rgba(239, 68, 68, ${opacity})`,
      color: opacity > 0.5 ? "#fff" : "#f87171",
    };
  }
}

function formatReturn(returnPct: number | null): string {
  if (returnPct === null) return "—";
  return `${returnPct >= 0 ? "+" : ""}${returnPct.toFixed(1)}%`;
}

export function ReturnsHeatmap({ items }: ReturnsHeatmapProps) {
  if (!items || items.length === 0) return null;

  const allReturns = items.map((item) => ({
    ticker: item.ticker,
    monthlyReturns: computeMonthlyReturns(item),
  }));

  // Check if we have data
  const hasData = allReturns.some((r) => r.monthlyReturns.length > 0);
  if (!hasData) {
    return (
      <div className="rounded-lg border border-[#1e2d3a] bg-[#0d1319] p-6 text-center">
        <p className="text-sm text-[#6b7f8e]">
          No price history data available for heatmap.
        </p>
      </div>
    );
  }

  // Use the maximum number of months across all tickers
  const maxMonths = Math.max(
    ...allReturns.map((r) => r.monthlyReturns.length),
    0
  );

  return (
    <div className="rounded-lg border border-[#1e2d3a] bg-[#0d1319] p-4">
      <div className="overflow-x-auto">
        <div
          className="grid gap-1"
          style={{
            gridTemplateColumns: `100px repeat(${maxMonths}, 60px)`,
          }}
        >
          {/* Empty top-left cell */}
          <div className="text-xs font-medium text-[#6b7f8e] p-1.5"></div>

          {/* Month headers */}
          {Array.from({ length: maxMonths }).map((_, colIdx) => {
            // Get month label from any ticker that has data at this column
            const label =
              allReturns.find(
                (r) => r.monthlyReturns.length > colIdx
              )?.monthlyReturns[colIdx]?.label ?? "";
            return (
              <div
                key={`header-${colIdx}`}
                className="text-xs font-medium text-[#6b7f8e] text-center p-1.5 truncate"
                title={label}
              >
                {label}
              </div>
            );
          })}

          {/* Ticker rows */}
          {allReturns.map((item) => (
            <>
              {/* Ticker label */}
              <div
                key={`label-${item.ticker}`}
                className="text-sm font-semibold text-[#c8d8e4] p-1.5 flex items-center"
              >
                {item.ticker}
              </div>

              {/* Return cells */}
              {Array.from({ length: maxMonths }).map((_, colIdx) => {
                const monthlyReturn = item.monthlyReturns[colIdx];
                const returnPct = monthlyReturn?.returnPct ?? null;
                const style = getCellStyle(returnPct);
                return (
                  <div
                    key={`cell-${item.ticker}-${colIdx}`}
                    className="text-xs font-mono text-center p-1.5 rounded-md cursor-default transition-opacity hover:opacity-80"
                    style={style}
                    title={
                      monthlyReturn
                        ? `${item.ticker} ${monthlyReturn.label}: ${formatReturn(returnPct)}`
                        : `${item.ticker}: No data`
                    }
                  >
                    {formatReturn(returnPct)}
                  </div>
                );
              })}
            </>
          ))}
        </div>
      </div>
    </div>
  );
}
