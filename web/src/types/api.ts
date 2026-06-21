// ─── Market Data ───────────────────────────────────────────────

export interface MarketIndex {
  name: string;
  value: number;
  change: number;
  change_pct: number;
}

export interface MacroIndicator {
  vix: number | null;
  yield_curve: { [key: string]: number } | null;
  credit_spread: number | null;
  dollar_index: number | null;
}

export interface MarketNewsItem {
  title: string;
  source: string;
  published: string;
  url: string;
  summary?: string;
}

// ─── Company Data ──────────────────────────────────────────────

export interface CompanyOverview {
  ticker: string;
  name: string;
  sector: string;
  industry: string;
  price: number;
  change: number;
  change_pct: number;
  market_cap: number;
}

export interface HealthScore {
  score: number; // 0-100
  verdict: string; // "Strong" | "Moderate" | "Weak"
  fscore: number; // 0-9 Piotroski
  criteria: [string, boolean, string][];
}

export interface ZScoreResult {
  score: number | null;
  zone: "Safe" | "Grey" | "Distress" | "Unknown";
  explanation: string;
  x1: number;
  x2: number;
  x3: number;
  x4: number;
}

export interface RiskAssessment {
  score: number; // 0-100 (higher = lower risk)
  label: "Low" | "Medium" | "High";
  summary: string;
  factors: [string, string, string][]; // [severity, title, explanation]
}

export interface RedFlag {
  severity: "danger" | "warning";
  title: string;
  explanation: string;
}

export interface DCFResult {
  error: string | null;
  current_revenue: number | null;
  current_fcf: number | null;
  current_fcf_margin: number | null;
  shares_outstanding: number | null;
  projected_revenue: number[];
  projected_fcf: number[];
  pv_fcf: number[];
  terminal_value: number | null;
  pv_terminal: number | null;
  enterprise_value: number | null;
  fair_value_per_share: number | null;
  fair_value_with_cash: number | null;
  net_cash_per_share: number | null;
  upside_pct: number | null;
  verdict: string;
  sensitivity: {
    wacc_range: number[];
    growth_range: number[];
    matrix: (number | null)[][];
    current_price: number | null;
  };
  assumptions: {
    revenue_growth_5yr: number;
    terminal_growth: number;
    discount_rate: number;
    margin_improvement: number;
  };
}

export interface IntrinsicWorth {
  score: number;
  verdict: string;
  explanation: string;
  notes: string;
  breakdown: {
    graham_ratio: number | null;
    graham_number: number | null;
    fcf_yield: number | null;
    pb_ratio: number | null;
    earnings_power_value: number | null;
    epv_ratio: number | null;
    dividend_yield: number | null;
  };
}

export interface FinancialStatements {
  income: { label: string; values: Record<string, number> }[];
  balance: { label: string; values: Record<string, number> }[];
  cashflow: { label: string; values: Record<string, number> }[];
}

export interface PriceCandle {
  time: string;
  open: number;
  high: number;
  low: number;
  close: number;
}

export interface PriceGrowth {
  growth_3m: number | null;
  growth_6m: number | null;
  growth_12m: number | null;
}

// ─── Watchlist ─────────────────────────────────────────────────

export interface WatchlistItem {
  ticker: string;
  name: string;
  sector: string;
  industry: string;
  price: number;
  change: number;
  change_pct: number;
  health_score: number;
  verdict: string;
  risk_label: string;
  growth_3m: number | null;
  growth_6m: number | null;
  growth_12m: number | null;
}

// ─── User & Auth ───────────────────────────────────────────────

export interface User {
  id: number;
  username: string;
  display_name: string | null;
  email: string | null;
  telegram_chat_id: string | null;
}

export type UserSummary = Omit<User, "telegram_chat_id">;

export interface NotificationPrefs {
  health_change: boolean;
  verdict_change: boolean;
  risk_flag_change: boolean;
  zscore_zone_change: boolean;
  fscore_change: boolean;
  check_interval_hours: number;
  health_delta_threshold: number;
}

// ─── API Responses ─────────────────────────────────────────────

export type ApiResponse<T> = {
  ok?: boolean;
  error?: string;
} & T;

// ─── Notifications ─────────────────────────────────────────────

export interface NotificationItem {
  id: string;
  ticker: string;
  message: string;
  severity: "info" | "warning" | "critical";
  timestamp: string;
  read: boolean;
  dismissed: boolean;
}

// ─── Alerts ────────────────────────────────────────────────────

export interface AlertCondition {
  signal_category: string;
  signal: string;
  operator: string;
  value: number;
  days?: number;
  period?: string;
}

export interface AlertRule {
  id: string;
  name: string;
  severity: "info" | "warning" | "critical";
  scope: "watchlist" | "single";
  ticker?: string;
  conditions: AlertCondition[];
  logic: "AND" | "OR";
  enabled: boolean;
  created_at: string;
}

export interface SignalEntry {
  id: string;
  name: string;
  category: string;
  value_type: "number";
  requires_days?: boolean;
  requires_period?: boolean;
}

// ─── Screener ──────────────────────────────────────────────────

export interface ScreenerResult {
  ticker: string;
  name: string;
  price: number;
  marketCap: number;
  pe: number | null;
  volume: number;
  change: number;
  healthScore: number;
  verdict: string;
}

// ─── SEC Filings & Insider ─────────────────────────────────────

export interface Filing {
  ticker: string;
  type: string;
  date: string;
  link: string;
}

export interface InsiderTrade {
  ticker: string;
  name: string;
  title: string;
  transaction: "Buy" | "Sell";
  shares: number;
  value: number;
  date: string;
}

// ─── Sectors ───────────────────────────────────────────────────

export interface SectorResult {
  ticker: string;
  name: string;
  sector: string;
  industry: string;
  price: number;
  marketCap: number;
  pe: number | null;
  change: number;
  healthScore: number;
}

// ─── Admin ─────────────────────────────────────────────────────

export interface AdminUser {
  id: number;
  username: string;
  email: string | null;
  telegram_chat_id: string | null;
  last_login: string | null;
  created_at: string;
}
