"use client";

import { PieChart, Pie, Cell, ResponsiveContainer, Tooltip, Legend } from "recharts";

interface SectorData {
  name: string;
  count: number;
}

interface SectorPieProps {
  data: SectorData[];
}

const COLORS = ["#84cc16", "#22c55e", "#eab308", "#ef4444", "#8b5cf6", "#f97316", "#06b6d4", "#ec4899", "#6366f1"];

export function SectorPie({ data }: SectorPieProps) {
  if (data.length === 0) {
    return (
      <div className="flex items-center justify-center h-[250px] text-[#6b7f8e] text-sm">
        No sector data available
      </div>
    );
  }

  return (
    <ResponsiveContainer width="100%" height={250}>
      <PieChart>
        <Pie
          data={data}
          cx="50%"
          cy="50%"
          outerRadius={80}
          dataKey="count"
          nameKey="name"
          label={({ name, percent }) => `${name} ${(percent * 100).toFixed(0)}%`}
          labelLine={false}
        >
          {data.map((entry, index) => (
            <Cell key={index} fill={COLORS[index % COLORS.length]} />
          ))}
        </Pie>
        <Tooltip
          contentStyle={{
            backgroundColor: "#111922",
            border: "1px solid #1e2d3a",
            borderRadius: "12px",
            color: "#f0f4f0",
          }}
        />
        <Legend
          wrapperStyle={{ color: "#6b7f8e", fontSize: "12px" }}
        />
      </PieChart>
    </ResponsiveContainer>
  );
}