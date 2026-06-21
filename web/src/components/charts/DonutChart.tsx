"use client";

import { PieChart, Pie, Cell, ResponsiveContainer } from "recharts";

interface DonutChartProps {
  data: { name: string; value: number }[];
  size?: number;
  thickness?: number;
}

const COLORS = ["#84cc16", "#65a30d", "#22c55e", "#eab308", "#ef4444", "#8b5cf6", "#f97316", "#06b6d4"];

export function DonutChart({ data, size = 180, thickness = 28 }: DonutChartProps) {
  const total = data.reduce((s, d) => s + d.value, 0);

  return (
    <ResponsiveContainer width={size} height={size}>
      <PieChart>
        <Pie
          data={data}
          cx="50%"
          cy="50%"
          innerRadius={size / 2 - thickness}
          outerRadius={size / 2}
          paddingAngle={2}
          dataKey="value"
          nameKey="name"
          stroke="none"
        >
          {data.map((entry, index) => (
            <Cell key={index} fill={COLORS[index % COLORS.length]} />
          ))}
        </Pie>
        {/* Center text overlay */}
        <text x="50%" y="45%" textAnchor="middle" fill="#f0f4f0" fontSize="20" fontWeight="bold">
          {total >= 1000 ? `${(total / 1000).toFixed(1)}k` : total}
        </text>
        <text x="50%" y="58%" textAnchor="middle" fill="#6b7f8e" fontSize="10">
          Total
        </text>
      </PieChart>
    </ResponsiveContainer>
  );
}
