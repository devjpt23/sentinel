"use client";

import type { CompareItem } from "@/types/api";
import {
  Table,
  TableHeader,
  TableBody,
  TableHead,
  TableRow,
  TableCell,
} from "@/components/ui/table";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Popover,
  PopoverTrigger,
  PopoverContent,
} from "@/components/ui/popover";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { useCompareStore } from "@/stores/compare-store";
import {
  formatPrice,
  formatCurrency,
  formatPct,
  getHealthColor,
} from "@/lib/utils";
import { Download, Settings2 } from "lucide-react";

interface MetricDef {
  key: string;
  label: string;
  format: (item: CompareItem) => string;
  color: (item: CompareItem) => string;
}

const METRICS: MetricDef[] = [
  {
    key: "price",
    label: "Price",
    format: (i) => formatPrice(i.price),
    color: () => "",
  },
  {
    key: "market_cap",
    label: "Market Cap",
    format: (i) => formatCurrency(i.market_cap),
    color: () => "",
  },
  {
    key: "pe_ratio",
    label: "P/E",
    format: (i) => (i.pe_ratio !== null ? i.pe_ratio.toFixed(2) : "N/A"),
    color: () => "",
  },
  {
    key: "health_score",
    label: "Health Score",
    format: (i) => `${i.health_score}/100`,
    color: (i) => getHealthColor(i.health_score),
  },
  {
    key: "risk_score",
    label: "Risk Score",
    format: (i) => `${i.risk_score}/100`,
    color: (i) => {
      if (i.risk_score >= 70) return "text-emerald-400";
      if (i.risk_score >= 40) return "text-yellow-400";
      return "text-red-400";
    },
  },
  {
    key: "fscore",
    label: "F-Score",
    format: (i) => `${i.fscore}/9`,
    color: (i) => {
      if (i.fscore >= 7) return "text-emerald-400";
      if (i.fscore >= 5) return "text-yellow-400";
      return "text-red-400";
    },
  },
  {
    key: "zscore",
    label: "Z-Score",
    format: (i) => (i.zscore !== null ? i.zscore.toFixed(2) : "N/A"),
    color: (i) => {
      if (i.zscore === null) return "";
      if (i.zscore >= 2.99) return "text-emerald-400";
      if (i.zscore >= 1.81) return "text-yellow-400";
      return "text-red-400";
    },
  },
  {
    key: "growth_3m",
    label: "3M Growth",
    format: (i) => (i.growth_3m !== null ? formatPct(i.growth_3m) : "N/A"),
    color: (i) =>
      i.growth_3m !== null
        ? i.growth_3m >= 0
          ? "text-emerald-400"
          : "text-red-400"
        : "",
  },
  {
    key: "growth_6m",
    label: "6M Growth",
    format: (i) => (i.growth_6m !== null ? formatPct(i.growth_6m) : "N/A"),
    color: (i) =>
      i.growth_6m !== null
        ? i.growth_6m >= 0
          ? "text-emerald-400"
          : "text-red-400"
        : "",
  },
  {
    key: "growth_12m",
    label: "12M Growth",
    format: (i) => (i.growth_12m !== null ? formatPct(i.growth_12m) : "N/A"),
    color: (i) =>
      i.growth_12m !== null
        ? i.growth_12m >= 0
          ? "text-emerald-400"
          : "text-red-400"
        : "",
  },
  {
    key: "fair_value",
    label: "Fair Value",
    format: (i) => (i.fair_value !== null ? formatPrice(i.fair_value) : "N/A"),
    color: () => "",
  },
  {
    key: "upside_pct",
    label: "Upside %",
    format: (i) => (i.upside_pct !== null ? formatPct(i.upside_pct) : "N/A"),
    color: (i) =>
      i.upside_pct !== null
        ? i.upside_pct >= 0
          ? "text-emerald-400"
          : "text-red-400"
        : "",
  },
];

interface CompareTableProps {
  items: CompareItem[];
  isLoading: boolean;
}

export function CompareTable({ items, isLoading }: CompareTableProps) {
  const visibleMetrics = useCompareStore((s) => s.visibleMetrics);
  const setVisibleMetrics = useCompareStore((s) => s.setVisibleMetrics);

  // Filter metrics by visibility
  const filteredMetrics = METRICS.filter((m) => visibleMetrics.includes(m.key));

  const handleExportCSV = () => {
    if (items.length === 0) return;

    // Header row
    const headers = ["Metric", ...items.map((i) => i.ticker)];
    const rows = filteredMetrics.map((metric) => [
      metric.label,
      ...items.map((item) => {
        const raw = metric.format(item);
        // Remove $ signs for clean CSV, wrap in quotes if comma
        const clean = raw.replace(/\$/g, "");
        return clean.includes(",") ? `"${clean}"` : clean;
      }),
    ]);

    const csvContent = [
      headers.join(","),
      ...rows.map((r) => r.join(",")),
    ].join("\n");

    const blob = new Blob([csvContent], { type: "text/csv;charset=utf-8;" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;

    const date = new Date().toISOString().split("T")[0];
    const tickerStr = items
      .slice(0, 2)
      .map((i) => i.ticker)
      .join("-vs-");
    link.download = `compare-${tickerStr}-${date}.csv`;

    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
  };

  const handleToggleMetric = (key: string) => {
    if (visibleMetrics.includes(key)) {
      // Don't allow hiding all metrics
      if (visibleMetrics.length <= 1) return;
      setVisibleMetrics(visibleMetrics.filter((k) => k !== key));
    } else {
      setVisibleMetrics([...visibleMetrics, key]);
    }
  };

  if (isLoading) {
    return (
      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-base">Comparison Table</CardTitle>
        </CardHeader>
        <CardContent className="p-0">
          <div className="space-y-2 p-4">
            {Array.from({ length: 8 }).map((_, i) => (
              <Skeleton key={i} className="h-8 w-full" />
            ))}
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
          <CardTitle className="text-base">Comparison Table</CardTitle>
          <div className="flex items-center gap-1">
            {/* Export CSV */}
            <Button
              variant="ghost"
              size="sm"
              onClick={handleExportCSV}
              className="text-xs text-[#6b7f8e] hover:text-[#84cc16] gap-1"
            >
              <Download className="h-3.5 w-3.5" />
              Export CSV
            </Button>

            {/* Column customization */}
            <Popover>
              <PopoverTrigger asChild>
                <Button
                  variant="ghost"
                  size="icon"
                  className="h-7 w-7 text-[#6b7f8e] hover:text-[#84cc16]"
                >
                  <Settings2 className="h-4 w-4" />
                </Button>
              </PopoverTrigger>
              <PopoverContent
                align="end"
                className="w-56 p-3"
              >
                <p className="text-xs font-medium text-[#6b7f8e] mb-2">
                  Visible Metrics
                </p>
                <div className="space-y-1.5">
                  {METRICS.map((metric) => (
                    <label
                      key={metric.key}
                      className="flex items-center gap-2 cursor-pointer text-sm text-[#c8d8e4] hover:text-[#f0f4f0]"
                    >
                      <Checkbox
                        checked={visibleMetrics.includes(metric.key)}
                        onCheckedChange={() => handleToggleMetric(metric.key)}
                      />
                      {metric.label}
                    </label>
                  ))}
                </div>
              </PopoverContent>
            </Popover>
          </div>
        </div>
      </CardHeader>
      <CardContent className="p-0 overflow-x-auto">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead className="w-48 sticky left-0 bg-[#0a0e13] z-10">
                Metric
              </TableHead>
              {items.map((item) => (
                <TableHead
                  key={item.ticker}
                  className="text-center min-w-[100px]"
                >
                  <span className="text-[#84cc16] font-semibold">
                    {item.ticker}
                  </span>
                </TableHead>
              ))}
            </TableRow>
          </TableHeader>
          <TableBody>
            {filteredMetrics.map((metric) => (
              <TableRow key={metric.key}>
                <TableCell className="font-medium text-[#6b7f8e] sticky left-0 bg-[#0a0e13] z-10">
                  {metric.label}
                </TableCell>
                {items.map((item) => (
                  <TableCell
                    key={`${metric.key}-${item.ticker}`}
                    className={`text-center font-mono ${metric.color(item)}`}
                  >
                    {metric.format(item)}
                  </TableCell>
                ))}
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </CardContent>
    </Card>
  );
}
