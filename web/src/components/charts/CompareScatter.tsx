"use client"

import { useState, useMemo } from "react"
import {
  ScatterChart,
  Scatter,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  ZAxis,
} from "recharts"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import type { CompareItem } from "@/types/api"

// ── Axis definitions ──────────────────────────────────────────────

interface AxisDef {
  key: string
  label: string
  available: boolean
  /** Extract numeric value from CompareItem. Returns null when unavailable. */
  extract: (item: CompareItem) => number | null
}

const X_AXES: AxisDef[] = [
  {
    key: "pe_ratio",
    label: "P/E",
    available: true,
    extract: (i) => i.pe_ratio,
  },
  {
    key: "market_cap",
    label: "Market Cap",
    available: true,
    extract: (i) => i.market_cap,
  },
  {
    key: "debt_equity",
    label: "Debt/Equity",
    available: false,
    extract: () => null,
  },
  {
    key: "pb_ratio",
    label: "P/B",
    available: false,
    extract: () => null,
  },
  {
    key: "dividend_yield",
    label: "Dividend Yield",
    available: false,
    extract: () => null,
  },
]

const Y_AXES: AxisDef[] = [
  {
    key: "health_score",
    label: "Health Score",
    available: true,
    extract: (i) => i.health_score,
  },
  {
    key: "growth",
    label: "Growth %",
    available: true,
    extract: (i) => {
      const g3 = i.growth_3m ?? 0
      const g6 = i.growth_6m ?? 0
      const g12 = i.growth_12m ?? 0
      return parseFloat(((g3 + g6 + g12) / 3).toFixed(1))
    },
  },
  {
    key: "roe",
    label: "ROE",
    available: false,
    extract: () => null,
  },
  {
    key: "risk_score",
    label: "Risk Score",
    available: true,
    extract: (i) => i.risk_score,
  },
  {
    key: "fscore",
    label: "F-Score",
    available: true,
    extract: (i) => i.fscore,
  },
]

// ── Sector colour palette ─────────────────────────────────────────

const SECTOR_COLORS = [
  "#3b82f6",
  "#84cc16",
  "#f59e0b",
  "#ef4444",
  "#8b5cf6",
  "#06b6d4",
  "#f97316",
  "#ec4899",
  "#14b8a6",
  "#a855f7",
]

function sectorColor(sector: string): string {
  let hash = 0
  for (let i = 0; i < sector.length; i++) {
    hash = sector.charCodeAt(i) + ((hash << 5) - hash)
  }
  return SECTOR_COLORS[Math.abs(hash) % SECTOR_COLORS.length]
}

// ── Tooltip ───────────────────────────────────────────────────────

interface ScatterTipPayload {
  ticker: string
  sector: string
  x: number | null
  y: number | null
  fill: string
}

function ScatterTooltip({
  active,
  payload,
  xLabel,
  yLabel,
}: {
  active?: boolean
  payload?: { payload: ScatterTipPayload }[]
  xLabel: string
  yLabel: string
}) {
  if (!active || !payload || payload.length === 0) return null
  const d = payload[0].payload
  return (
    <div className="rounded-lg border border-[#1e2d3a] bg-[#111922] px-3 py-2 text-xs shadow-md">
      <p className="font-semibold text-[#f0f4f0]">{d.ticker}</p>
      <p className="text-[#6b7f8e] mt-0.5">{d.sector}</p>
      <div className="mt-1 space-y-0.5">
        <p>
          <span className="text-[#6b7f8e]">{xLabel}: </span>
          <span className="text-[#f0f4f0]">
            {d.x !== null ? formatAxisValue(xLabel, d.x) : "N/A"}
          </span>
        </p>
        <p>
          <span className="text-[#6b7f8e]">{yLabel}: </span>
          <span className="text-[#f0f4f0]">
            {d.y !== null ? formatAxisValue(yLabel, d.y) : "N/A"}
          </span>
        </p>
      </div>
    </div>
  )
}

function formatAxisValue(label: string, value: number): string {
  if (label === "Market Cap") {
    if (value >= 1e12) return `$${(value / 1e12).toFixed(2)}T`
    if (value >= 1e9) return `$${(value / 1e9).toFixed(2)}B`
    if (value >= 1e6) return `$${(value / 1e6).toFixed(2)}M`
    return `$${value.toLocaleString()}`
  }
  if (label === "Growth %") return `${value}%`
  return String(value)
}

// ── Component ─────────────────────────────────────────────────────

interface CompareScatterProps {
  items: CompareItem[]
}

export function CompareScatter({ items }: CompareScatterProps) {
  const [xKey, setXKey] = useState("pe_ratio")
  const [yKey, setYKey] = useState("health_score")

  const xAxis = X_AXES.find((a) => a.key === xKey) ?? X_AXES[0]
  const yAxis = Y_AXES.find((a) => a.key === yKey) ?? Y_AXES[0]

  const hasData = xAxis.available && yAxis.available

  const scatterData = useMemo(() => {
    if (!hasData) return []
    return items.map((item) => ({
      ticker: item.ticker,
      sector: item.sector,
      x: xAxis.extract(item),
      y: yAxis.extract(item),
      fill: sectorColor(item.sector),
    }))
  }, [items, xAxis, yAxis, hasData])

  const hasPoints = scatterData.some((d) => d.x !== null && d.y !== null)

  return (
    <Card>
      <CardHeader className="pb-2">
        <div className="flex items-center justify-between">
          <CardTitle className="text-base">Scatter Comparison</CardTitle>
          <div className="flex items-center gap-3">
            <div className="flex items-center gap-1.5">
              <span className="text-xs text-[#6b7f8e]">X:</span>
              <Select value={xKey} onValueChange={setXKey}>
                <SelectTrigger className="h-7 w-[130px] text-xs">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {X_AXES.map((a) => (
                    <SelectItem key={a.key} value={a.key} className="text-xs">
                      {a.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="flex items-center gap-1.5">
              <span className="text-xs text-[#6b7f8e]">Y:</span>
              <Select value={yKey} onValueChange={setYKey}>
                <SelectTrigger className="h-7 w-[130px] text-xs">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {Y_AXES.map((a) => (
                    <SelectItem key={a.key} value={a.key} className="text-xs">
                      {a.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          </div>
        </div>
      </CardHeader>

      <CardContent>
        {!hasData || !hasPoints ? (
          <div className="flex items-center justify-center h-[350px] text-[#6b7f8e] text-sm">
            {!hasData
              ? "Data not yet available for this axis combination"
              : "No data points to display"}
          </div>
        ) : (
          <ResponsiveContainer width="100%" height={350}>
            <ScatterChart margin={{ top: 10, right: 20, bottom: 20, left: 10 }}>
              <CartesianGrid stroke="rgba(30,45,58,0.6)" />
              <XAxis
                type="number"
                dataKey="x"
                name={xAxis.label}
                stroke="#6b7f8e"
                tick={{ fill: "#6b7f8e", fontSize: 11 }}
                label={{
                  value: xAxis.label,
                  position: "insideBottom",
                  offset: -10,
                  fill: "#6b7f8e",
                  fontSize: 11,
                }}
              />
              <YAxis
                type="number"
                dataKey="y"
                name={yAxis.label}
                stroke="#6b7f8e"
                tick={{ fill: "#6b7f8e", fontSize: 11 }}
                label={{
                  value: yAxis.label,
                  angle: -90,
                  position: "insideLeft",
                  fill: "#6b7f8e",
                  fontSize: 11,
                }}
              />
              <ZAxis range={[80, 80]} />
              <Tooltip
                content={
                  <ScatterTooltip
                    xLabel={xAxis.label}
                    yLabel={yAxis.label}
                  />
                }
                cursor={{ stroke: "rgba(107,127,142,0.3)", strokeDasharray: "4 4" }}
              />
              <Scatter
                name="Stocks"
                data={scatterData}
                shape={(props: any) => {
                  const { cx, cy, fill } = props
                  return (
                    <g>
                      {cx !== undefined && cy !== undefined && (
                        <>
                          <circle
                            cx={cx}
                            cy={cy}
                            r={7}
                            fill={fill}
                            stroke="rgba(0,0,0,0.3)"
                            strokeWidth={1}
                          />
                          <text
                            x={cx}
                            y={cy - 12}
                            textAnchor="middle"
                            fill="#c8d8e4"
                            fontSize={10}
                            fontWeight={500}
                          >
                            {props.payload.ticker}
                          </text>
                        </>
                      )}
                    </g>
                  )
                }}
              />
            </ScatterChart>
          </ResponsiveContainer>
        )}
      </CardContent>
    </Card>
  )
}
