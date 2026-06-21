// Sentinel constants

export const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_URL || "http://localhost:5252";

export const SESSION_COOKIE_NAME = "session";
export const SESSION_MAX_AGE = 2592000; // 30 days in seconds

// =================== Sectors ===================

export const SECTORS = [
  "Technology",
  "Healthcare",
  "Financial Services",
  "Consumer Cyclical",
  "Industrials",
  "Communication Services",
  "Consumer Defensive",
  "Energy",
  "Utilities",
  "Real Estate",
  "Basic Materials",
] as const;

export type SectorName = (typeof SECTORS)[number];

// =================== Countries for Screener ===================

export const COUNTRIES = [
  "United States",
  "Canada",
  "United Kingdom",
  "Germany",
  "France",
  "Japan",
  "China",
  "India",
  "Australia",
  "South Korea",
  "Switzerland",
  "Netherlands",
  "Sweden",
  "Brazil",
  "Singapore",
  "Hong Kong",
  "Israel",
] as const;

export type CountryName = (typeof COUNTRIES)[number];

// =================== Signal Categories ===================

export const SIGNAL_CATEGORIES = [
  "Price Movement",
  "Volume Spike",
  "Technical Indicator",
  "Fundamental Change",
  "News & Sentiment",
  "Insider Activity",
  "Institutional Activity",
  "Earnings",
  "Dividend",
] as const;

export const SIGNAL_TYPES = [
  { id: "price_above", name: "Price Above Threshold", category: "Price Movement", defaultCondition: "above", defaultThreshold: 0 },
  { id: "price_below", name: "Price Below Threshold", category: "Price Movement", defaultCondition: "below", defaultThreshold: 0 },
  { id: "price_change_pct", name: "Daily Change %", category: "Price Movement", defaultCondition: "above", defaultThreshold: 5 },
  { id: "volume_spike", name: "Volume Spike", category: "Volume Spike", defaultCondition: "above", defaultThreshold: 200 },
  { id: "volume_drop", name: "Volume Drop", category: "Volume Spike", defaultCondition: "below", defaultThreshold: 50 },
  { id: "rsi_oversold", name: "RSI Oversold", category: "Technical Indicator", defaultCondition: "below", defaultThreshold: 30 },
  { id: "rsi_overbought", name: "RSI Overbought", category: "Technical Indicator", defaultCondition: "above", defaultThreshold: 70 },
  { id: "ma_crossover", name: "Moving Average Crossover", category: "Technical Indicator", defaultCondition: "equals", defaultThreshold: 0 },
  { id: "health_score_change", name: "Health Score Change", category: "Fundamental Change", defaultCondition: "below", defaultThreshold: 50 },
  { id: "risk_level_change", name: "Risk Level Change", category: "Fundamental Change", defaultCondition: "equals", defaultThreshold: 0 },
  { id: "news_sentiment", name: "News Sentiment Shift", category: "News & Sentiment", defaultCondition: "below", defaultThreshold: -0.5 },
  { id: "insider_buying", name: "Insider Buying", category: "Insider Activity", defaultCondition: "above", defaultThreshold: 0 },
  { id: "insider_selling", name: "Insider Selling", category: "Insider Activity", defaultCondition: "above", defaultThreshold: 0 },
  { id: "institutional_flow", name: "Institutional Flow", category: "Institutional Activity", defaultCondition: "above", defaultThreshold: 0 },
  { id: "earnings_surprise", name: "Earnings Surprise", category: "Earnings", defaultCondition: "above", defaultThreshold: 10 },
  { id: "dividend_change", name: "Dividend Change", category: "Dividend", defaultCondition: "below", defaultThreshold: 0 },
  { id: "new_52w_high", name: "New 52-Week High", category: "Price Movement", defaultCondition: "equals", defaultThreshold: 0 },
  { id: "new_52w_low", name: "New 52-Week Low", category: "Price Movement", defaultCondition: "equals", defaultThreshold: 0 },
] as const;

// =================== Nav Items ===================

export const NAV_ITEMS = [
  { id: "dashboard", label: "Dashboard", icon: "layout-dashboard", href: "/" },
  { id: "watchlist", label: "Watchlist", icon: "eye", href: "/watchlist" },
  { id: "sectors", label: "Sectors", icon: "layers", href: "/sectors" },
  { id: "screener", label: "Screener", icon: "filter", href: "/screener" },
  { id: "filings", label: "SEC Filings", icon: "file-text", href: "/sec-filings" },
  { id: "notifications", label: "Notifications", icon: "bell", href: "/notifications" },
  { id: "alerts", label: "Alerts", icon: "alert-triangle", href: "/alerts" },
  { id: "settings", label: "Settings", icon: "settings", href: "/settings" },
  { id: "admin", label: "Admin", icon: "shield", href: "/admin" },
  { id: "about", label: "About", icon: "info", href: "/about" },
] as const;

// =================== Color Helpers ===================

export const VERDICT_COLORS: Record<string, string> = {
  "Strong Buy": "bg-green-500/20 text-green-400 border-green-500/30",
  "Buy": "bg-green-500/10 text-green-400 border-green-500/20",
  "Hold": "bg-yellow-500/10 text-yellow-400 border-yellow-500/20",
  "Sell": "bg-red-500/10 text-red-400 border-red-500/20",
  "Strong Sell": "bg-red-500/20 text-red-400 border-red-500/30",
};

export const SEVERITY_COLORS: Record<string, string> = {
  info: "bg-blue-500/10 text-blue-400 border-blue-500/20",
  warning: "bg-yellow-500/10 text-yellow-400 border-yellow-500/20",
  critical: "bg-red-500/10 text-red-400 border-red-500/20",
};

export const RISK_COLORS: Record<string, string> = {
  Low: "text-green-400",
  Moderate: "text-yellow-400",
  High: "text-orange-400",
  "Very High": "text-red-400",
};
