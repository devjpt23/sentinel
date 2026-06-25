import type { SignalEntry } from "@/types/api";

// ─── Extended Interface ──────────────────────────────────────────────

export interface CatalogEntry extends SignalEntry {
  description: string;
  unit: string;
  operators: string[];
  requires_history?: boolean;
}

// ─── Signal Catalog ──────────────────────────────────────────────────

export const SIGNAL_CATALOG: CatalogEntry[] = [
  // ── Price & Volume ──────────────────────────────────────────────
  {
    id: "price",
    name: "Current Price",
    category: "Price & Volume",
    value_type: "number",
    description: "The latest trading price",
    unit: "USD",
    operators: [">", "<", ">=", "<=", "==", "crosses_above", "crosses_below"],
    requires_history: false,
  },
  {
    id: "price_change_abs",
    name: "Price Change ($)",
    category: "Price & Volume",
    value_type: "number",
    description:
      "Absolute dollar change over N trading days (+ means up, - means down)",
    unit: "USD",
    operators: [">", "<", ">=", "<=", "crosses_above", "crosses_below"],
    requires_history: true,
    requires_days: true,
  },
  {
    id: "price_change_pct",
    name: "Price Change %",
    category: "Price & Volume",
    value_type: "number",
    description: "Percent change over N trading days",
    unit: "%",
    operators: [">", "<", ">=", "<="],
    requires_history: true,
    requires_days: true,
  },
  {
    id: "distance_52w_high",
    name: "% Below 52-Week High",
    category: "Price & Volume",
    value_type: "number",
    description: "How far below the 52-week high (0% = at high)",
    unit: "%",
    operators: [">", "<", ">=", "<="],
    requires_history: false,
  },
  {
    id: "distance_52w_low",
    name: "% Above 52-Week Low",
    category: "Price & Volume",
    value_type: "number",
    description: "How far above the 52-week low (0% = at low)",
    unit: "%",
    operators: [">", "<", ">=", "<="],
    requires_history: false,
  },
  {
    id: "volume_spike",
    name: "Volume vs Average",
    category: "Price & Volume",
    value_type: "number",
    description: "Current daily volume divided by average volume",
    unit: "×",
    operators: [">", "<", ">=", "<="],
    requires_history: true,
  },
  {
    id: "sma_crossover",
    name: "Price vs SMA",
    category: "Price & Volume",
    value_type: "number",
    description: "Price relative to Simple Moving Average",
    unit: "",
    operators: ["crosses_above", "crosses_below"],
    requires_history: true,
    requires_period: true,
  },

  // ── Technical ───────────────────────────────────────────────────
  {
    id: "rsi",
    name: "RSI (14)",
    category: "Technical",
    value_type: "number",
    description:
      "Relative Strength Index, 0-100. Above 70 = overbought, below 30 = oversold",
    unit: "",
    operators: [">", "<", ">=", "<=", "crosses_above", "crosses_below"],
    requires_history: true,
  },
  {
    id: "macd",
    name: "MACD Signal Cross",
    category: "Technical",
    value_type: "number",
    description:
      "MACD line crossing the signal line (bullish/bearish)",
    unit: "",
    operators: ["crosses_above", "crosses_below"],
    requires_history: true,
  },
  {
    id: "bollinger",
    name: "Bollinger Band Touch",
    category: "Technical",
    value_type: "number",
    description:
      "Price touching upper or lower Bollinger Band (20,2)",
    unit: "",
    operators: ["touches_upper", "touches_lower"],
    requires_history: true,
  },

  // ── Fundamental ─────────────────────────────────────────────────
  {
    id: "health_score",
    name: "Health Score",
    category: "Fundamental",
    value_type: "number",
    description: "Composite financial health score (0-100)",
    unit: "pts",
    operators: [">", "<", ">=", "<=", "crosses_above", "crosses_below"],
    requires_history: false,
  },
  {
    id: "fscore",
    name: "F-Score",
    category: "Fundamental",
    value_type: "number",
    description: "Piotroski F-Score (0-9)",
    unit: "pts",
    operators: [">", "<", ">=", "<="],
    requires_history: false,
  },
  {
    id: "risk_score",
    name: "Risk Score",
    category: "Fundamental",
    value_type: "number",
    description: "Risk assessment score (0-100, higher = safer)",
    unit: "pts",
    operators: [">", "<", ">=", "<="],
    requires_history: false,
  },
  {
    id: "zscore",
    name: "Altman Z-Score",
    category: "Fundamental",
    value_type: "number",
    description:
      "Bankruptcy risk score. >2.6 Safe, 1.1-2.6 Grey, <1.1 Distress",
    unit: "",
    operators: [">", "<", ">=", "<="],
    requires_history: false,
  },
  {
    id: "pe_ttm",
    name: "P/E Ratio (TTM)",
    category: "Fundamental",
    value_type: "number",
    description: "Price to trailing twelve months earnings",
    unit: "×",
    operators: [">", "<", ">=", "<="],
    requires_history: false,
  },
  {
    id: "pb_ratio",
    name: "P/B Ratio",
    category: "Fundamental",
    value_type: "number",
    description: "Price to book value",
    unit: "×",
    operators: [">", "<", ">=", "<="],
    requires_history: false,
  },
  {
    id: "debt_to_equity",
    name: "Debt/Equity Ratio",
    category: "Fundamental",
    value_type: "number",
    description: "Total debt divided by equity (as %)",
    unit: "%",
    operators: [">", "<", ">=", "<="],
    requires_history: false,
  },
  {
    id: "dividend_yield",
    name: "Dividend Yield",
    category: "Fundamental",
    value_type: "number",
    description: "Annual dividend yield (as %)",
    unit: "%",
    operators: [">", "<", ">=", "<="],
    requires_history: false,
  },
  {
    id: "red_flag_count",
    name: "Red Flag Count",
    category: "Fundamental",
    value_type: "number",
    description: "Number of active danger + warning flags",
    unit: "flags",
    operators: [">", "<", ">=", "<=", "=="],
    requires_history: false,
  },

  // ── News ──────────────────────────────────────────────────────
  {
    id: "new_news",
    name: "New News Article",
    category: "News",
    value_type: "boolean",
    description:
      "A new news article was published for this ticker (checked every ~15 min)",
    unit: "",
    operators: ["=="],
    requires_history: false,
  },
  {
    id: "new_industry_news",
    name: "Industry News Activity",
    category: "News",
    value_type: "number",
    description:
      "New news across all tickers in your watchlist's sectors (checked every ~15 min)",
    unit: "articles",
    operators: [">", ">=", "=="],
    requires_history: false,
  },
];

// ─── Categories ──────────────────────────────────────────────────────

export const SIGNAL_CATEGORIES: string[] = [
  "Price & Volume",
  "Technical",
  "Fundamental",
  "News",
];

// ─── Grouped by Category ─────────────────────────────────────────────

export const SIGNAL_CATALOG_BY_CATEGORY: Record<string, CatalogEntry[]> =
  SIGNAL_CATALOG.reduce<Record<string, CatalogEntry[]>>((acc, signal) => {
    if (!acc[signal.category]) {
      acc[signal.category] = [];
    }
    acc[signal.category].push(signal);
    return acc;
  }, {});

// ─── Helper Functions ────────────────────────────────────────────────

export function getSignalById(id: string): CatalogEntry | undefined {
  return SIGNAL_CATALOG.find((s) => s.id === id);
}

export function getSignalsByCategory(category: string): CatalogEntry[] {
  return SIGNAL_CATALOG_BY_CATEGORY[category] ?? [];
}
