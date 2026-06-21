"use client";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { ScoreBadge } from "@/components/shared/ScoreBadge";
import { VerdictBadge } from "@/components/shared/VerdictBadge";
import { RiskBadge } from "@/components/shared/RiskBadge";
import { formatPrice } from "@/lib/utils";

interface HealthCardProps {
  ticker: string;
  name: string;
  sector: string;
  price: number;
  changePct: number;
  healthScore: number;
  verdict: string;
  riskLabel: string;
  growth3m: number | null;
  growth6m: number | null;
  growth12m: number | null;
  onClick?: () => void;
}

export function HealthCard({
  ticker, name, sector, price, changePct,
  healthScore, verdict, riskLabel, growth3m, growth6m, growth12m, onClick,
}: HealthCardProps) {
  const growths = [
    { label: "3M", value: growth3m },
    { label: "6M", value: growth6m },
    { label: "12M", value: growth12m },
  ];

  return (
    <Card
      className="cursor-pointer transition-all duration-200 hover:border-[#2a3f52] hover:shadow-lg hover:shadow-[#84cc16]/5"
      onClick={onClick}
    >
      <CardHeader className="pb-3">
        <div className="flex items-start justify-between">
          <div>
            <CardTitle className="text-lg text-[#f0f4f0]">{ticker}</CardTitle>
            <p className="text-xs text-[#6b7f8e] mt-0.5 truncate max-w-[160px]">{name}</p>
          </div>
          <ScoreBadge score={healthScore} size="md" />
        </div>
        <p className="text-xs text-[#6b7f8e]">{sector}</p>
      </CardHeader>
      <CardContent className="space-y-3">
        {/* Price */}
        <div className="flex items-center justify-between">
          <span className="text-lg font-semibold text-[#f0f4f0]">{formatPrice(price)}</span>
          <span className={`text-sm font-medium ${changePct >= 0 ? "text-[#84cc16]" : "text-red-400"}`}>
            {changePct >= 0 ? "+" : ""}{changePct.toFixed(2)}%
          </span>
        </div>

        {/* Badges */}
        <div className="flex gap-2">
          <VerdictBadge verdict={verdict} />
          <RiskBadge label={riskLabel} />
        </div>

        {/* Growth sparkline placeholders */}
        <div className="flex gap-2">
          {growths.map((g) => (
            <div key={g.label} className="flex-1 text-center">
              <p className="text-[10px] text-[#6b7f8e]">{g.label}</p>
              <p className={`text-sm font-medium ${
                g.value === null ? "text-[#3a5570]" :
                g.value >= 0 ? "text-[#84cc16]" : "text-red-400"
              }`}>
                {g.value !== null ? `${g.value >= 0 ? "+" : ""}${g.value.toFixed(1)}%` : "N/A"}
              </p>
            </div>
          ))}
        </div>

        {/* Mini sparkline visualization */}
        <Sparkline values={[growth3m, growth6m, growth12m]} />
      </CardContent>
    </Card>
  );
}

function Sparkline({ values }: { values: (number | null)[] }) {
  const validValues = values.filter((v): v is number => v !== null);
  if (validValues.length === 0) {
    return (
      <div className="flex items-center justify-center h-6 text-xs text-[#3a5570]">
        No price history
      </div>
    );
  }

  const min = Math.min(...validValues);
  const max = Math.max(...validValues);
  const range = max - min || 1;

  const points = validValues.map((v, i) => {
    const x = (i / (validValues.length - 1 || 1)) * 100;
    const y = 24 - ((v - min) / range) * 20 - 2;
    return `${x},${y}`;
  }).join(" ");

  const isPositive = validValues[validValues.length - 1] >= validValues[0];

  return (
    <svg viewBox="0 0 100 24" className="w-full h-6" preserveAspectRatio="none">
      <polyline
        fill="none"
        stroke={isPositive ? "#84cc16" : "#ef4444"}
        strokeWidth="2"
        points={points}
      />
    </svg>
  );
}