import { type ClassValue, clsx } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function formatCurrency(value: number | null | undefined): string {
  if (value === null || value === undefined) return "N/A";
  if (Math.abs(value) >= 1e12) return `$${(value / 1e12).toFixed(2)}T`;
  if (Math.abs(value) >= 1e9) return `$${(value / 1e9).toFixed(2)}B`;
  if (Math.abs(value) >= 1e6) return `$${(value / 1e6).toFixed(2)}M`;
  if (Math.abs(value) >= 1e3) return `$${(value / 1e3).toFixed(2)}K`;
  return `$${value.toFixed(2)}`;
}

export function formatPercent(value: number | null | undefined, decimals = 2): string {
  if (value === null || value === undefined) return "N/A";
  return `${(value * 100).toFixed(decimals)}%`;
}

export function formatPct(value: number | null | undefined, decimals = 2): string {
  if (value === null || value === undefined) return "N/A";
  return `${value >= 0 ? "+" : ""}${value.toFixed(decimals)}%`;
}

export function formatNumber(value: number | null | undefined): string {
  if (value === null || value === undefined) return "N/A";
  return value.toLocaleString();
}

export function formatRelativeTime(dateStr: string): string {
  if (!dateStr) return "Never";
  // Handle SQLite format: "YYYY-MM-DD HH:MM:SS" → ISO 8601
  const normalized = dateStr.replace(" ", "T");
  const now = new Date();
  const date = new Date(normalized);
  if (isNaN(date.getTime())) return "Invalid date";
  const diffMs = now.getTime() - date.getTime();
  const diffHrs = Math.floor(diffMs / (1000 * 60 * 60));
  const diffDays = Math.floor(diffMs / (1000 * 60 * 60 * 24));

  if (diffHrs < 1) return "Just now";
  if (diffHrs < 24) return `${diffHrs}h ago`;
  if (diffDays < 7) return `${diffDays}d ago`;
  return date.toLocaleDateString();
}

export function getHealthColor(score: number): string {
  if (score >= 70) return "text-emerald-400";
  if (score >= 40) return "text-yellow-400";
  return "text-red-400";
}

export function getHealthBg(score: number): string {
  if (score >= 70) return "bg-emerald-500/20 text-emerald-400 border-emerald-500/30";
  if (score >= 40) return "bg-yellow-500/20 text-yellow-400 border-yellow-500/30";
  return "bg-red-500/20 text-red-400 border-red-500/30";
}

export function getHealthBarColor(score: number): string {
  if (score >= 70) return "bg-emerald-500";
  if (score >= 40) return "bg-yellow-500";
  return "bg-red-500";
}

export function getVerdictInfo(verdict: string) {
  const lower = verdict.toLowerCase();
  if (lower.includes("strong") || lower.includes("healthy") || lower.includes("undervalued")) {
    return { color: "text-emerald-400", bg: "bg-emerald-500/20 border-emerald-500/30" };
  }
  if (lower.includes("moderate") || lower.includes("fair") || lower.includes("slightly")) {
    return { color: "text-yellow-400", bg: "bg-yellow-500/20 border-yellow-500/30" };
  }
  return { color: "text-red-400", bg: "bg-red-500/20 border-red-500/30" };
}

export function getRiskColor(label: string): string {
  const lower = label.toLowerCase();
  if (lower === "low") return "text-emerald-400";
  if (lower === "medium") return "text-yellow-400";
  return "text-red-400";
}

export function getRiskBg(label: string): string {
  const lower = label.toLowerCase();
  if (lower === "low") return "bg-emerald-500/20 text-emerald-400 border-emerald-500/30";
  if (lower === "medium") return "bg-yellow-500/20 text-yellow-400 border-yellow-500/30";
  return "bg-red-500/20 text-red-400 border-red-500/30";
}

export function getZScoreZoneColor(zone: string): string {
  if (zone === "Safe") return "text-emerald-400";
  if (zone === "Grey") return "text-yellow-400";
  if (zone === "Distress") return "text-red-400";
  return "text-gray-400";
}

export function getSensitivityCellColor(value: number | null): string {
  if (value === null) return "bg-gray-800 text-gray-600";
  if (value > 30) return "bg-emerald-600 text-white";
  if (value > 15) return "bg-emerald-500/70 text-white";
  if (value > 5) return "bg-emerald-400/50 text-white";
  if (value > -5) return "bg-yellow-500/40 text-white";
  if (value > -15) return "bg-orange-500/50 text-white";
  if (value > -30) return "bg-red-500/60 text-white";
  return "bg-red-600 text-white";
}

export function formatPrice(value: number): string {
  return `$${value.toFixed(2)}`;
}

// ─── Overview Card Signal Colors ──────────────────────────────────

export function getSignalColor(verdict: string): string {
  const lower = verdict.toLowerCase();
  if (lower.includes("cheap") || lower.includes("bullish") || lower.includes("buying") ||
      lower.includes("accumulat") || lower.includes("strong") || lower.includes("uptrend") ||
      lower.includes("calm")) return "text-emerald-400";
  if (lower.includes("expensive") || lower.includes("bearish") || lower.includes("selling") ||
      lower.includes("distribut") || lower.includes("weak") || lower.includes("downtrend") ||
      lower.includes("fearful")) return "text-red-400";
  return "text-yellow-400"; // fair, mixed, neutral, normal, choppy, etc.
}

export function getSignalBg(verdict: string): string {
  const lower = verdict.toLowerCase();
  if (lower.includes("cheap") || lower.includes("bullish") || lower.includes("buying") ||
      lower.includes("accumulat") || lower.includes("strong") || lower.includes("uptrend") ||
      lower.includes("calm")) return "bg-emerald-500/20 border-emerald-500/30";
  if (lower.includes("expensive") || lower.includes("bearish") || lower.includes("selling") ||
      lower.includes("distribut") || lower.includes("weak") || lower.includes("downtrend") ||
      lower.includes("fearful")) return "bg-red-500/20 border-red-500/30";
  return "bg-yellow-500/20 border-yellow-500/30";
}

// ─── Regime Detector ──────────────────────────────────────────────
// Combines VIX, S&P trend, and yield curve into a single market regime verdict.
// Pure function — no side effects, easily testable.

export interface RegimeInput {
  vix?: { verdict?: string };
  sp500?: { verdict?: string };
  yieldCurve?: { verdict?: string };
}

export interface RegimeResult {
  verdict: "Bullish" | "Neutral" | "Bearish" | "Unknown";
  vixVerdict?: string;
  spTrend?: string;
  yieldVerdict?: string;
}

// ─── Supply Chain Helpers ─────────────────────────────────────────

export function getInvestabilityColor(score: number): string {
  if (score >= 70) return "text-emerald-400";
  if (score >= 40) return "text-yellow-400";
  return "text-red-400";
}

export function getRiskLabel(score: number): string {
  if (score >= 70) return "Strong";
  if (score >= 40) return "Moderate";
  return "Weak";
}

export function formatLargeNumber(value: number | null | undefined): string {
  if (value === null || value === undefined) return "N/A";
  if (Math.abs(value) >= 1e12) return `${(value / 1e12).toFixed(2)}T`;
  if (Math.abs(value) >= 1e9) return `${(value / 1e9).toFixed(2)}B`;
  if (Math.abs(value) >= 1e6) return `${(value / 1e6).toFixed(2)}M`;
  if (Math.abs(value) >= 1e3) return `${(value / 1e3).toFixed(2)}K`;
  return value.toFixed(2);
}

export function computeRegime(macro: Record<string, unknown> | undefined, indices: { name: string; change_pct: number }[] | undefined): RegimeResult {
  const vixVerdict = (macro?.vix as { verdict?: string })?.verdict;
  const spTrend = (macro?.sp500 as { verdict?: string })?.verdict;
  const yieldVerdict = (macro?.yieldCurve as { verdict?: string })?.verdict;

  // Bullish: calm VIX + uptrend + normal yield curve
  const isCalm = vixVerdict?.toLowerCase() === "calm";
  const isUptrend = spTrend?.toLowerCase() === "uptrend";
  const isNormalYield = yieldVerdict?.toLowerCase().includes("normal");

  // Bearish: fearful VIX OR downtrend OR inverted yield
  const isFearful = vixVerdict?.toLowerCase() === "fearful";
  const isDowntrend = spTrend?.toLowerCase() === "downtrend";
  const isInverted = yieldVerdict?.toLowerCase().includes("inverted");

  if (isCalm && isUptrend && isNormalYield) {
    return { verdict: "Bullish", vixVerdict, spTrend, yieldVerdict };
  }
  if (isFearful || isDowntrend || isInverted) {
    return { verdict: "Bearish", vixVerdict, spTrend, yieldVerdict };
  }
  if (vixVerdict || spTrend) {
    return { verdict: "Neutral", vixVerdict, spTrend, yieldVerdict };
  }
  return { verdict: "Unknown" };
}
