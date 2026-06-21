// Domain types for Sentinel financial dashboard

export interface Stock {
  ticker: string;
  name: string;
  sector: string;
  industry: string;
  country: string;
  marketCap: number;
  price: number;
  change: number;
  changePercent: number;
  volume: number;
  avgVolume: number;
  peRatio: number | null;
  eps: number | null;
  dividend: number | null;
  dividendYield: number | null;
  beta: number | null;
  high52w: number | null;
  low52w: number | null;
}

export interface Quote {
  ticker: string;
  price: number;
  change: number;
  changePercent: number;
  volume: number;
  timestamp: string;
  open: number;
  high: number;
  low: number;
  previousClose: number;
}

export interface HealthScore {
  ticker: string;
  overallScore: number; // 0-100
  financialHealth: number; // 0-100
  profitability: number; // 0-100
  growth: number; // 0-100
  valuation: number; // 0-100
  momentum: number; // 0-100
  fScore: number; // 0-9 Piotroski F-Score
  verdict: "Strong Buy" | "Buy" | "Hold" | "Sell" | "Strong Sell";
  lastUpdated: string;
}

export interface IntrinsicValue {
  ticker: string;
  grahamNumber: number | null;
  grahamGrowthValue: number | null;
  dcfValue: number | null;
  fcfValue: number | null;
  consensusValue: number | null;
  currentPrice: number;
  upside: number; // percentage
  methods: Array<{
    method: string;
    value: number | null;
    upside: number | null;
  }>;
  lastUpdated: string;
}

export interface RiskAssessment {
  ticker: string;
  riskScore: number; // 0-100, higher = riskier
  riskLevel: "Low" | "Moderate" | "High" | "Very High";
  volatility: number;
  maxDrawdown: number;
  sharpeRatio: number | null;
  redFlags: RiskFlag[];
  lastUpdated: string;
}

export interface RiskFlag {
  category: string;
  description: string;
  severity: "low" | "medium" | "high" | "critical";
}

export interface PeerComparison {
  ticker: string;
  peers: PeerData[];
  metrics: string[];
}

export interface PeerData {
  ticker: string;
  name: string;
  pe: number | null;
  pb: number | null;
  ps: number | null;
  evEbitda: number | null;
  marketCap: number;
  revenueGrowth: number | null;
  profitMargin: number | null;
  roe: number | null;
  debtToEquity: number | null;
}

export interface PriceGrowth {
  ticker: string;
  oneMonth: number;
  threeMonth: number;
  sixMonth: number;
  twelveMonth: number;
  ytd: number;
}

export interface FinancialStatement {
  ticker: string;
  currency: string;
  periods: FinancialPeriod[];
}

export interface FinancialPeriod {
  period: string; // e.g. "2024-Q4"
  fiscalYear: number;
  fiscalQuarter: number | null;
  data: Record<string, number | null>;
}

export interface DCFModel {
  ticker: string;
  fairValue: number;
  currentPrice: number;
  upside: number;
  assumptions: {
    revenueGrowthRate: number;
    terminalGrowthRate: number;
    wacc: number;
    forecastYears: number;
  };
  projections: DCFProjection[];
  sensitivity: {
    waccRange: number[];
    growthRange: number[];
    matrix: number[][];
  };
}

export interface DCFProjection {
  year: number;
  revenue: number;
  ebitda: number;
  fcf: number;
  presentValue: number;
}

export interface SentimentData {
  ticker: string;
  newsScore: number; // -1 to 1
  newsArticles: NewsArticle[];
  analystConsensus: AnalystConsensus;
  socialSentiment: number | null;
}

export interface NewsArticle {
  title: string;
  source: string;
  url: string;
  publishedAt: string;
  sentiment: "positive" | "negative" | "neutral";
  score: number;
}

export interface AnalystConsensus {
  buy: number;
  hold: number;
  sell: number;
  targetPrice: number | null;
  targetHigh: number | null;
  targetLow: number | null;
  targetMedian: number | null;
}

export interface InstitutionalHolder {
  name: string;
  shares: number;
  value: number;
  percentOfPortfolio: number | null;
  change: number | null;
  changePercent: number | null;
}

export interface SupplyChainRelationship {
  company: string;
  ticker: string | null;
  relationship: "supplier" | "customer" | "both";
  country: string;
  riskScore: number | null;
}

export interface Filing {
  id: string;
  ticker: string;
  formType: string;
  filedDate: string;
  description: string;
  url: string;
  size: string;
}

export interface InsiderTrade {
  ticker: string;
  insiderName: string;
  title: string;
  transactionType: "buy" | "sell" | "option_exercise" | "grant";
  shares: number;
  price: number | null;
  value: number | null;
  date: string;
  sharesOwned: number | null;
}

export interface EcosystemNode {
  ticker: string;
  name: string;
  type: "company" | "supplier" | "customer" | "competitor";
  riskScore: number | null;
}

export interface EcosystemLink {
  source: string;
  target: string;
  relationship: string;
}

export interface EcosystemData {
  ticker: string;
  nodes: EcosystemNode[];
  links: EcosystemLink[];
  insights: string[];
}

export interface Sector {
  name: string;
  industries: string[];
  companies: SectorCompany[];
}

export interface SectorCompany {
  ticker: string;
  name: string;
  industry: string;
  marketCap: number;
}

export interface AlertRule {
  id: string;
  userId: string;
  ticker: string;
  signalType: string;
  condition: string;
  threshold: number;
  enabled: boolean;
  channels: ("telegram" | "email")[];
  createdAt: string;
  lastTriggered: string | null;
}

export interface Notification {
  id: string;
  userId: string;
  title: string;
  message: string;
  type: "alert" | "system" | "news" | "price";
  severity: "info" | "warning" | "critical";
  read: boolean;
  dismissed: boolean;
  createdAt: string;
  ticker: string | null;
}

export interface User {
  id: string;
  email: string;
  name: string;
  telegramId: string | null;
  telegramUsername: string | null;
  createdAt: string;
  lastActive: string;
  preferences: UserPreferences;
}

export interface UserPreferences {
  emailNotifications: boolean;
  telegramNotifications: boolean;
  alertFrequency: "instant" | "hourly" | "daily";
  watchlistRefresh: boolean;
}

export interface MacroIndicator {
  name: string;
  value: number;
  change: number;
  changePercent: number;
  description: string;
}

export interface MarketIndex {
  name: string;
  symbol: string;
  value: number;
  change: number;
  changePercent: number;
}

export interface MarketMover {
  ticker: string;
  name: string;
  price: number;
  change: number;
  changePercent: number;
  volume: number;
  reason: string;
}

export interface ScreenerResult {
  ticker: string;
  name: string;
  sector: string;
  price: number;
  changePercent: number;
  marketCap: number;
  pe: number | null;
  volume: number;
  healthScore: number | null;
}
