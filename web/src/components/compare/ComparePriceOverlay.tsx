"use client";

import { useEffect, useRef, useState } from "react";
import { createChart, ColorType, type IChartApi, type ISeriesApi, type UTCTimestamp } from "lightweight-charts";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import type { CompareItem } from "@/types/api";

const CHART_COLORS = [
  "#84cc16", // lime-green
  "#3b82f6", // blue
  "#f59e0b", // amber
  "#ef4444", // red
  "#8b5cf6", // violet
  "#06b6d4", // cyan
  "#f97316", // orange
  "#ec4899", // pink
  "#14b8a6", // teal
  "#a855f7", // purple
];

const PERIODS = ["1M", "3M", "6M", "1Y"] as const;
type Period = (typeof PERIODS)[number];

function getPeriodDays(period: Period): number {
  switch (period) {
    case "1M": return 30;
    case "3M": return 90;
    case "6M": return 180;
    case "1Y": return 365;
  }
}

interface ComparePriceOverlayProps {
  items: CompareItem[];
  isLoading: boolean;
}

export function ComparePriceOverlay({ items, isLoading }: ComparePriceOverlayProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const seriesRef = useRef<ISeriesApi<"Line">[]>([]);
  const [period, setPeriod] = useState<Period>("1Y");

  useEffect(() => {
    if (!containerRef.current || items.length === 0) return;

    // Clean up previous chart
    seriesRef.current.forEach((s) => chartRef.current?.removeSeries(s));
    seriesRef.current = [];
    if (chartRef.current) {
      chartRef.current.remove();
      chartRef.current = null;
    }

    const chart = createChart(containerRef.current, {
      layout: {
        background: { type: ColorType.Solid, color: "transparent" },
        textColor: "#6b7f8e",
      },
      grid: {
        vertLines: { color: "rgba(30,45,58,0.5)" },
        horzLines: { color: "rgba(30,45,58,0.5)" },
      },
      width: containerRef.current.clientWidth,
      height: 350,
      timeScale: {
        borderColor: "rgba(30,45,58,0.7)",
        timeVisible: false,
      },
      rightPriceScale: {
        borderColor: "rgba(30,45,58,0.7)",
      },
      crosshair: {
        vertLine: { color: "rgba(30,45,58,0.7)", width: 1, style: 0, labelBackgroundColor: "#1a2a38" },
        horzLine: { color: "rgba(30,45,58,0.7)", width: 1, style: 0, labelBackgroundColor: "#1a2a38" },
      },
    });

    chartRef.current = chart;

    const periodDays = getPeriodDays(period);
    const cutoff = Date.now() - periodDays * 24 * 60 * 60 * 1000;

    items.forEach((item, i) => {
      if (!item.price_history || item.price_history.length === 0) return;

      const lineSeries = chart.addLineSeries({
        color: CHART_COLORS[i % CHART_COLORS.length],
        lineWidth: 2,
        priceLineVisible: false,
        lastValueVisible: true,
        title: item.ticker,
      });

      const filtered = item.price_history.filter((d) => {
        const ts = new Date(d.date).getTime();
        return ts >= cutoff;
      });

      const chartData = filtered.map((d) => ({
        time: (new Date(d.date).getTime() / 1000) as UTCTimestamp,
        value: d.price,
      }));

      lineSeries.setData(chartData);
      seriesRef.current.push(lineSeries);
    });

    chart.timeScale().fitContent();

    const handleResize = () => {
      if (containerRef.current) {
        chart.applyOptions({ width: containerRef.current.clientWidth });
      }
    };
    window.addEventListener("resize", handleResize);

    return () => {
      window.removeEventListener("resize", handleResize);
      chart.remove();
      chartRef.current = null;
      seriesRef.current = [];
    };
  }, [items, period]);

  if (isLoading) {
    return (
      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-base">Price Overlay</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex items-center justify-center h-[350px]">
            <Skeleton className="h-full w-full" />
          </div>
        </CardContent>
      </Card>
    );
  }

  if (items.length === 0) {
    return null;
  }

  return (
    <Card>
      <CardHeader className="pb-2">
        <div className="flex items-center justify-between">
          <CardTitle className="text-base">Price Overlay</CardTitle>
          <div className="flex gap-1">
            {PERIODS.map((p) => (
              <button
                key={p}
                onClick={() => setPeriod(p)}
                className={`px-2 py-1 text-xs rounded-md transition-colors ${
                  p === period
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
        {/* Legend */}
        <div className="flex flex-wrap gap-3 mb-3">
          {items.map((item, i) => (
            <div key={item.ticker} className="flex items-center gap-1.5">
              <div
                className="h-2.5 w-2.5 rounded-full"
                style={{ backgroundColor: CHART_COLORS[i % CHART_COLORS.length] }}
              />
              <span className="text-xs text-[#c8d8e4] font-medium">{item.ticker}</span>
            </div>
          ))}
        </div>
        <div ref={containerRef} className="w-full" />
      </CardContent>
    </Card>
  );
}
