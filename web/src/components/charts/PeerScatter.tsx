"use client";

import {
  ScatterChart,
  Scatter,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Cell,
} from "recharts";

interface PeerData {
  name: string;
  healthScore: number;
  riskScore: number;
}

interface PeerScatterProps {
  data: PeerData[];
}

export function PeerScatter({ data }: PeerScatterProps) {
  if (data.length === 0) {
    return (
      <div className="flex items-center justify-center h-[250px] text-[#6b7f8e] text-sm">
        No peer data available
      </div>
    );
  }

  return (
    <ResponsiveContainer width="100%" height={250}>
      <ScatterChart>
        <CartesianGrid stroke="rgba(30,45,58,0.6)" />
        <XAxis
          type="number"
          dataKey="riskScore"
          name="Risk Score"
          stroke="#6b7f8e"
          tick={{ fill: "#6b7f8e", fontSize: 12 }}
          label={{ value: "Risk Score", position: "insideBottom", offset: -5, fill: "#6b7f8e", fontSize: 12 }}
        />
        <YAxis
          type="number"
          dataKey="healthScore"
          name="Health Score"
          stroke="#6b7f8e"
          tick={{ fill: "#6b7f8e", fontSize: 12 }}
          label={{ value: "Health Score", angle: -90, position: "insideLeft", fill: "#6b7f8e", fontSize: 12 }}
        />
        <Tooltip
          contentStyle={{
            backgroundColor: "#111922",
            border: "1px solid #1e2d3a",
            borderRadius: "12px",
            color: "#f0f4f0",
          }}
          formatter={(value: number, name: string) => [value, name]}
        />
        <Scatter name="Peers" data={data}>
          {data.map((entry, index) => (
            <Cell
              key={index}
              fill={entry.healthScore >= 70 ? "#84cc16" : entry.healthScore >= 40 ? "#eab308" : "#ef4444"}
            />
          ))}
        </Scatter>
      </ScatterChart>
    </ResponsiveContainer>
  );
}