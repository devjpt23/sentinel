"use client"

import {
  RadarChart,
  Radar,
  PolarGrid,
  PolarAngleAxis,
  PolarRadiusAxis,
  ResponsiveContainer,
  Legend,
} from "recharts"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import type { CompareItem } from "@/types/api"

const RADAR_COLORS = ["#84cc16", "#3b82f6", "#f59e0b", "#ef4444", "#8b5cf6"]

const AXES = ["Value", "Health", "Growth", "Profitability", "Safety", "Momentum"] as const

interface CompareRadarProps {
  items: CompareItem[]
}

function computeRadarData(items: CompareItem[]) {
  // Normalize each axis to 0-100 within the group, then build
  // Recharts-compatible data: [{ axis, ticker1: score1, ticker2: score2 }, ...]

  const tickers = items.map((i) => i.ticker)
  const rawScores: Record<string, Record<string, number>> = {}
  for (const t of tickers) {
    rawScores[t] = {}
  }

  // ── Value (P/E, lower is better) ──────────────────────────────
  const peValues = items
    .filter((i) => i.pe_ratio !== null && i.pe_ratio > 0)
    .map((i) => i.pe_ratio as number)
  const minPE = peValues.length > 0 ? Math.min(...peValues) : 0
  const maxPE = peValues.length > 0 ? Math.max(...peValues) : 1
  const peRange = maxPE - minPE || 1

  for (const item of items) {
    if (item.pe_ratio !== null && item.pe_ratio > 0) {
      rawScores[item.ticker].Value = Math.round(
        Math.max(0, Math.min(100, 100 - ((item.pe_ratio - minPE) / peRange) * 100)),
      )
    } else {
      rawScores[item.ticker].Value = 0
    }
  }

  // ── Health (0-100 directly) ───────────────────────────────────
  for (const item of items) {
    rawScores[item.ticker].Health = Math.round(
      Math.max(0, Math.min(100, item.health_score)),
    )
  }

  // ── Growth (average of 3m/6m/12m, normalized) ─────────────────
  const growthAvgs = items.map((item) => {
    const g3 = item.growth_3m ?? 0
    const g6 = item.growth_6m ?? 0
    const g12 = item.growth_12m ?? 0
    return (g3 + g6 + g12) / 3
  })
  const minG = Math.min(...growthAvgs)
  const maxG = Math.max(...growthAvgs)
  const rangeG = maxG - minG || 1

  for (let i = 0; i < items.length; i++) {
    rawScores[items[i].ticker].Growth = Math.round(
      Math.max(0, Math.min(100, ((growthAvgs[i] - minG) / rangeG) * 100)),
    )
  }

  // ── Profitability (F-score as proxy, 0-9 → 0-100) ────────────
  for (const item of items) {
    rawScores[item.ticker].Profitability = Math.round(
      Math.max(0, Math.min(100, (item.fscore / 9) * 100)),
    )
  }

  // ── Safety (100 - risk_score) ─────────────────────────────────
  for (const item of items) {
    rawScores[item.ticker].Safety = Math.round(
      Math.max(0, Math.min(100, 100 - item.risk_score)),
    )
  }

  // ── Momentum (average of 6m + 12m growth, normalized) ─────────
  const momValues = items.map((item) => {
    const g6 = item.growth_6m ?? 0
    const g12 = item.growth_12m ?? 0
    return (g6 + g12) / 2
  })
  const minMom = Math.min(...momValues)
  const maxMom = Math.max(...momValues)
  const rangeMom = maxMom - minMom || 1

  for (let i = 0; i < items.length; i++) {
    rawScores[items[i].ticker].Momentum = Math.round(
      Math.max(0, Math.min(100, ((momValues[i] - minMom) / rangeMom) * 100)),
    )
  }

  // Build rows: one per axis
  return AXES.map((axis) => {
    const row: Record<string, string | number> = { axis }
    for (const t of tickers) {
      row[t] = rawScores[t][axis] ?? 0
    }
    return row
  })
}

export function CompareRadar({ items }: CompareRadarProps) {
  if (items.length === 0) {
    return (
      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-base">Radar Comparison</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex items-center justify-center h-[350px] text-[#6b7f8e] text-sm">
            No tickers to compare
          </div>
        </CardContent>
      </Card>
    )
  }

  if (items.length > 5) {
    return (
      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-base">Radar Comparison</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex items-center justify-center h-[350px] text-[#6b7f8e] text-sm">
            Maximum 5 tickers for radar view
          </div>
        </CardContent>
      </Card>
    )
  }

  const radarData = computeRadarData(items)

  return (
    <Card>
      <CardHeader className="pb-2">
        <CardTitle className="text-base">Radar Comparison</CardTitle>
      </CardHeader>
      <CardContent>
        <ResponsiveContainer width="100%" height={350}>
          <RadarChart data={radarData}>
            <PolarGrid stroke="rgba(30,45,58,0.6)" />
            <PolarAngleAxis
              dataKey="axis"
              stroke="#6b7f8e"
              tick={{ fill: "#6b7f8e", fontSize: 12 }}
            />
            <PolarRadiusAxis
              angle={30}
              domain={[0, 100]}
              tick={{ fill: "#6b7f8e", fontSize: 10 }}
              stroke="rgba(30,45,58,0.6)"
              axisLine={false}
            />
            {items.map((item, i) => (
              <Radar
                key={item.ticker}
                name={item.ticker}
                dataKey={item.ticker}
                stroke={RADAR_COLORS[i % RADAR_COLORS.length]}
                fill={RADAR_COLORS[i % RADAR_COLORS.length]}
                fillOpacity={0.3}
              />
            ))}
            <Legend
              wrapperStyle={{ fontSize: 12, color: "#c8d8e4", paddingTop: 8 }}
            />
          </RadarChart>
        </ResponsiveContainer>
      </CardContent>
    </Card>
  )
}
