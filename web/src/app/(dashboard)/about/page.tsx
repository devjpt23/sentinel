"use client";

import { Shield, Bell, TrendingUp, Search, FileText, Users, Zap, Globe } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";

const features = [
  {
    icon: Shield,
    title: "Health Scoring",
    description: "Comprehensive financial health analysis using Piotroski F-Score, Altman Z-Score, and proprietary metrics to assess company strength.",
  },
  {
    icon: TrendingUp,
    title: "Intrinsic Value",
    description: "DCF models, Graham Number, FCF yield, and Earnings Power Value to determine if a stock is over or undervalued.",
  },
  {
    icon: Zap,
    title: "Risk Assessment",
    description: "Automated red flag detection with severity classification to warn you about potential financial risks.",
  },
  {
    icon: Bell,
    title: "Smart Alerts",
    description: "Custom alert rules with 18 signal types, condition builders, and instant Telegram notifications when thresholds are hit.",
  },
  {
    icon: Search,
    title: "Stock Screener",
    description: "Screen stocks across 17 countries with P/E, market cap, volume, and health score filters.",
  },
  {
    icon: FileText,
    title: "SEC Filings & Insider Trading",
    description: "Track 8-K, 10-Q, 10-K filings and insider buy/sell transactions for informed decision-making.",
  },
  {
    icon: Globe,
    title: "Sector Analysis",
    description: "Hierarchical sector and industry exploration with company metrics and quick analysis links.",
  },
  {
    icon: Users,
    title: "Watchlist Management",
    description: "Curate your portfolio watchlist with sortable metrics and peer comparisons.",
  },
];

export default function AboutPage() {
  return (
    <div className="space-y-8 max-w-4xl">
      <div>
        <h2 className="text-2xl font-bold text-[#f0f4f0]">About Sentinel</h2>
        <p className="text-[#6b7f8e] mt-2">
          Sentinel is a free, open-source stock analysis and alert platform that scores companies on
          financial health, risk, and fair value — delivering plain-language verdicts so you can
          act with confidence, not noise.
        </p>
      </div>

      {/* What is Sentinel */}
      <Card>
        <CardHeader>
          <CardTitle className="text-[#f0f4f0]">What is Sentinel?</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3 text-[#6b7f8e] leading-relaxed">
          <p>
            Sentinel continuously monitors your watchlist stocks using rigorous financial analysis
            frameworks. It scores each company on health, intrinsic value, and risk -- then delivers
            plain-language verdicts that any trader can understand.
          </p>
          <p>
            Instead of drowning in metrics, you get clear signals: whether a stock is fundamentally
            strong, fairly valued, or showing warning signs. Custom alerts fire via Telegram the moment
            conditions change, so you never miss a critical development.
          </p>
          <p>
            The alert engine runs 24/7 on a dedicated VPS daemon, ensuring no hibernation gaps or
            missed checks. You configure rules through this interface, and Sentinel does the watching.
          </p>
        </CardContent>
      </Card>

      {/* Features */}
      <div>
        <h3 className="text-lg font-semibold text-[#f0f4f0] mb-4">Features</h3>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {features.map((f) => (
            <Card key={f.title} className="hover:border-[#2a3f52] transition-colors">
              <CardHeader className="pb-3">
                <div className="flex items-center gap-3">
                  <div className="rounded-lg bg-[#1a2a38] p-2">
                    <f.icon className="h-5 w-5 text-[#84cc16]" />
                  </div>
                  <CardTitle className="text-[#f0f4f0] text-base">{f.title}</CardTitle>
                </div>
              </CardHeader>
              <CardContent>
                <CardDescription>{f.description}</CardDescription>
              </CardContent>
            </Card>
          ))}
        </div>
      </div>

      {/* Credits */}
      <Card>
        <CardHeader>
          <CardTitle className="text-[#f0f4f0]">Credits</CardTitle>
        </CardHeader>
        <CardContent className="space-y-2 text-[#6b7f8e] text-sm">
          <p>Built with:</p>
          <ul className="list-disc list-inside space-y-1">
            <li>Next.js 15 (App Router) + React 19</li>
            <li>Tailwind CSS v4 + shadcn/ui components</li>
            <li>TanStack React Query + Table</li>
            <li>Zustand for client state management</li>
            <li>Lucide React for icons</li>
            <li>TradingView Lightweight Charts for price charts</li>
            <li>Recharts for data visualization</li>
          </ul>
          <p className="mt-4">Data sources: SEC EDGAR, yfinance, OpenBB screener</p>
          <p>Alert delivery: Telegram Bot API</p>
          <p className="mt-4">Sentinel is open source and available on GitHub.</p>
          <p className="pt-2 text-[#3a5570]">
            Sentinel -- Automated stock analysis and monitoring.
          </p>
        </CardContent>
      </Card>
    </div>
  );
}