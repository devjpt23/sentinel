"use client";

import { AreaChart, Area, ResponsiveContainer } from "recharts";

interface MiniAreaChartProps {
  data: { value: number }[];
  color?: string;
  height?: number;
  width?: number;
}

export function MiniAreaChart({ data, color = "#84cc16", height = 60, width = 180 }: MiniAreaChartProps) {
  if (data.length === 0) return null;

  const isPositive = data[data.length - 1].value >= data[0].value;
  const fill = isPositive ? "#84cc16" : "#ef4444";

  return (
    <ResponsiveContainer width={width} height={height}>
      <AreaChart data={data} margin={{ top: 0, right: 0, bottom: 0, left: 0 }}>
        <defs>
          <linearGradient id={`gradient-${color}`} x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor={fill} stopOpacity={0.4} />
            <stop offset="100%" stopColor={fill} stopOpacity={0} />
          </linearGradient>
        </defs>
        <Area
          type="monotone"
          dataKey="value"
          stroke={fill}
          strokeWidth={1.5}
          fill={`url(#gradient-${color})`}
          dot={false}
          isAnimationActive={false}
        />
      </AreaChart>
    </ResponsiveContainer>
  );
}
