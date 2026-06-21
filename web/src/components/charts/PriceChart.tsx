"use client";

import { useEffect, useRef } from "react";
import { createChart, ColorType, type IChartApi, type ISeriesApi, type UTCTimestamp } from "lightweight-charts";

interface CandleData {
  time: UTCTimestamp;
  open: number;
  high: number;
  low: number;
  close: number;
}

interface VolumeData {
  time: UTCTimestamp;
  value: number;
  color: string;
}

interface PriceChartProps {
  candles: CandleData[];
  volumes?: VolumeData[];
  height?: number;
}

export function PriceChart({ candles, volumes, height = 350 }: PriceChartProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const seriesRef = useRef<ISeriesApi<"Candlestick"> | null>(null);

  useEffect(() => {
    if (!containerRef.current || candles.length === 0) return;

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
      height,
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

    const candleSeries = chart.addCandlestickSeries({
      upColor: "#84cc16",
      downColor: "#ef4444",
      borderUpColor: "#84cc16",
      borderDownColor: "#ef4444",
      wickUpColor: "#84cc16",
      wickDownColor: "#ef4444",
    });

    candleSeries.setData(candles);

    if (volumes && volumes.length > 0) {
      const volumeSeries = chart.addHistogramSeries({
        priceFormat: { type: "volume" },
        priceScaleId: "volume",
      });
      volumeSeries.priceScale().applyOptions({
        scaleMargins: { top: 0.8, bottom: 0 },
      });
      volumeSeries.setData(volumes);
    }

    chart.timeScale().fitContent();

    chartRef.current = chart;
    seriesRef.current = candleSeries;

    const handleResize = () => {
      if (containerRef.current) {
        chart.applyOptions({ width: containerRef.current.clientWidth });
      }
    };
    window.addEventListener("resize", handleResize);

    return () => {
      window.removeEventListener("resize", handleResize);
      chart.remove();
    };
  }, [candles, volumes, height]);

  if (candles.length === 0) {
    return (
      <div className="flex items-center justify-center h-[350px] text-[#6b7f8e] text-sm">
        No price data available
      </div>
    );
  }

  return <div ref={containerRef} className="w-full" />;
}