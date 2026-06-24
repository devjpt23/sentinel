"use client";

import {
  TrendingDown,
  Activity,
  TrendingUp,
  BarChart3,
  HeartPulse,
  ArrowUpRight,
  AlertTriangle,
  AlertCircle,
  CheckCircle2,
  Plus,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import type { AlertCondition } from "@/types/api";

// ─── Alert Template Types ────────────────────────────────────────────

export interface AlertTemplate {
  name: string;
  description: string;
  severity: "info" | "warning" | "critical";
  scope: "watchlist" | "single";
  ticker?: string;
  conditions: AlertCondition[];
  logic: "AND" | "OR";
}

// ─── Template Definitions ─────────────────────────────────────────────

interface TemplateDefinition extends AlertTemplate {
  icon: React.ElementType;
}

const TEMPLATES: TemplateDefinition[] = [
  {
    name: "Price Drop 5%",
    description: "Alerts when price drops 5% or more",
    severity: "warning",
    scope: "watchlist",
    conditions: [
      {
        signal_category: "Price & Volume",
        signal_id: "price_change_pct",
        operator: "<",
        value: -5,
      },
    ],
    logic: "AND",
    icon: TrendingDown,
  },
  {
    name: "RSI Oversold",
    description: "Alerts when RSI drops below 30 (oversold)",
    severity: "info",
    scope: "watchlist",
    conditions: [
      {
        signal_category: "Technical",
        signal_id: "rsi",
        operator: "<",
        value: 30,
      },
    ],
    logic: "AND",
    icon: Activity,
  },
  {
    name: "RSI Overbought",
    description: "Alerts when RSI rises above 70 (overbought)",
    severity: "warning",
    scope: "watchlist",
    conditions: [
      {
        signal_category: "Technical",
        signal_id: "rsi",
        operator: ">",
        value: 70,
      },
    ],
    logic: "AND",
    icon: TrendingUp,
  },
  {
    name: "Volume Spike 2x",
    description: "Alerts when volume is more than 2x average",
    severity: "info",
    scope: "watchlist",
    conditions: [
      {
        signal_category: "Price & Volume",
        signal_id: "volume_spike",
        operator: ">",
        value: 2,
      },
    ],
    logic: "AND",
    icon: BarChart3,
  },
  {
    name: "Health Score Below 50",
    description: "Alerts when health score drops below 50",
    severity: "critical",
    scope: "watchlist",
    conditions: [
      {
        signal_category: "Fundamental",
        signal_id: "health_score",
        operator: "<",
        value: 50,
      },
    ],
    logic: "AND",
    icon: HeartPulse,
  },
  {
    name: "MACD Bullish Cross",
    description: "Alerts on MACD bullish cross",
    severity: "info",
    scope: "watchlist",
    conditions: [
      {
        signal_category: "Technical",
        signal_id: "macd",
        operator: "crosses_above",
        value: 0,
      },
    ],
    logic: "AND",
    icon: ArrowUpRight,
  },
  {
    name: "Risk Flags Appear",
    description: "Alerts when any red flags are detected",
    severity: "warning",
    scope: "watchlist",
    conditions: [
      {
        signal_category: "Fundamental",
        signal_id: "red_flag_count",
        operator: ">",
        value: 0,
      },
    ],
    logic: "AND",
    icon: AlertTriangle,
  },
  {
    name: "Z-Score in Distress",
    description: "Alerts when Z-Score enters distress zone",
    severity: "critical",
    scope: "watchlist",
    conditions: [
      {
        signal_category: "Fundamental",
        signal_id: "zscore",
        operator: "<",
        value: 1.1,
      },
    ],
    logic: "AND",
    icon: AlertCircle,
  },
];

// ─── Severity Styling ─────────────────────────────────────────────────

const SEVERITY_STYLES: Record<
  AlertTemplate["severity"],
  { container: string; text: string }
> = {
  info: {
    container: "border-[#84cc16]/30 bg-[#84cc16]/20",
    text: "text-[#84cc16]",
  },
  warning: {
    container: "border-yellow-500/30 bg-yellow-500/20",
    text: "text-yellow-400",
  },
  critical: {
    container: "border-red-500/30 bg-red-500/20",
    text: "text-red-400",
  },
};

// ─── Icon Container Colors ────────────────────────────────────────────

const ICON_COLORS: Record<
  AlertTemplate["severity"],
  { bg: string; icon: string }
> = {
  info: { bg: "bg-[#84cc16]/20", icon: "text-[#84cc16]" },
  warning: { bg: "bg-yellow-500/20", icon: "text-yellow-400" },
  critical: { bg: "bg-red-500/20", icon: "text-red-400" },
};

// ─── Component ────────────────────────────────────────────────────────

interface QuickAlertsProps {
  onAdd: (template: AlertTemplate) => void;
  existingRuleNames?: string[];
}

export default function QuickAlerts({ onAdd, existingRuleNames = [] }: QuickAlertsProps) {
  const existingNames = new Set(existingRuleNames);
  return (
    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
      {TEMPLATES.map((template) => {
        const severityStyle = SEVERITY_STYLES[template.severity];
        const iconColor = ICON_COLORS[template.severity];
        const IconComponent = template.icon;

        return (
          <div
            key={template.name}
            className="rounded-lg border border-[#1e2d3a] bg-[#0d1319] p-4 hover:border-[#2a4a5a] transition-colors"
          >
            <div className="flex items-start justify-between mb-3">
              <div
                className={`rounded-full p-2 ${iconColor.bg} flex items-center justify-center`}
              >
                <IconComponent className={`h-4 w-4 ${iconColor.icon}`} />
              </div>
              <span
                className={`inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-medium ${severityStyle.container} ${severityStyle.text}`}
              >
                {template.severity}
              </span>
            </div>
            <h3 className="text-sm font-medium text-[#f0f4f0] mb-1">
              {template.name}
            </h3>
            <p className="text-xs text-[#6b7f8e] mb-4">
              {template.description}
            </p>
            {existingNames.has(template.name) ? (
              <div className="flex gap-2">
                <Button
                  variant="outline"
                  size="sm"
                  className="text-[#3a5570] w-full cursor-default"
                  disabled
                >
                  <CheckCircle2 className="h-3.5 w-3.5 mr-1" />
                  Already Added
                </Button>
              </div>
            ) : (
              <Button
                variant="outline"
                size="sm"
                className="text-[#84cc16] w-full"
                onClick={() => onAdd(template)}
              >
                <Plus className="h-3.5 w-3.5 mr-1" />
                Add Alert
              </Button>
            )}
          </div>
        );
      })}
    </div>
  );
}
