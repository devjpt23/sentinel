"use client";

import { useState } from "react";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { getSensitivityCellColor } from "@/lib/utils";

interface DcfHeatmapProps {
  sensitivity: {
    wacc_range: number[];
    growth_range: number[];
    matrix: (number | null)[][];
  } | null;
}

interface CellTooltip {
  wacc: number;
  growth: number;
  value: number | null;
  x: number;
  y: number;
}

export function DcfHeatmap({ sensitivity }: DcfHeatmapProps) {
  const [tooltip, setTooltip] = useState<CellTooltip | null>(null);

  if (!sensitivity) {
    return null;
  }

  const { wacc_range, growth_range, matrix } = sensitivity;

  if (!wacc_range?.length || !growth_range?.length || !matrix?.length) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Sensitivity Analysis — Upside %</CardTitle>
          <CardDescription>
            How upside changes with different WACC and growth assumptions
          </CardDescription>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-[#6b7f8e]">No sensitivity data available.</p>
        </CardContent>
      </Card>
    );
  }

  // Compute center indices for highlighting "current assumptions"
  const centerRow = Math.floor((growth_range.length - 1) / 2);
  const centerCol = Math.floor((wacc_range.length - 1) / 2);

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">Sensitivity Analysis — Upside %</CardTitle>
        <CardDescription>
          How upside changes with different WACC and growth assumptions
        </CardDescription>
      </CardHeader>
      <CardContent>
        <div className="overflow-x-auto">
          <div className="inline-block min-w-full">
            <table className="text-xs border-collapse">
              <thead>
                <tr>
                  <th className="p-2 text-[#6b7f8e] text-left font-normal whitespace-nowrap">
                    Growth \ WACC
                  </th>
                  {wacc_range.map((w: number, i: number) => (
                    <th
                      key={i}
                      className={`p-2 text-[#6b7f8e] font-mono font-normal text-center whitespace-nowrap ${
                        i === centerCol ? "border-b-2 border-[#84cc16]" : ""
                      }`}
                    >
                      {w.toFixed(1)}%
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {growth_range.map((g: number, rowI: number) => (
                  <tr key={rowI}>
                    <td
                      className={`p-2 text-[#6b7f8e] font-mono whitespace-nowrap ${
                        rowI === centerRow ? "border-r-2 border-[#84cc16]" : ""
                      }`}
                    >
                      {g.toFixed(1)}%
                    </td>
                    {matrix[rowI]?.map((val: number | null, colI: number) => {
                      const isCenterRow = rowI === centerRow;
                      const isCenterCol = colI === centerCol;
                      const isCenter = isCenterRow && isCenterCol;

                      return (
                        <td
                          key={colI}
                          className={`p-2 font-mono text-center rounded relative cursor-default ${
                            getSensitivityCellColor(val)
                          } ${
                            isCenter
                              ? "ring-2 ring-[#84cc16] ring-inset"
                              : ""
                          }`}
                          onMouseEnter={(e: React.MouseEvent) => {
                            setTooltip({
                              wacc: wacc_range[colI],
                              growth: growth_range[rowI],
                              value: val,
                              x: e.clientX,
                              y: e.clientY,
                            });
                          }}
                          onMouseMove={(e: React.MouseEvent) => {
                            setTooltip((prev) =>
                              prev
                                ? { ...prev, x: e.clientX, y: e.clientY }
                                : null
                            );
                          }}
                          onMouseLeave={() => {
                            setTooltip(null);
                          }}
                        >
                          {val !== null
                            ? `${val >= 0 ? "+" : ""}${val.toFixed(1)}%`
                            : "—"}
                        </td>
                      );
                    })}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        {tooltip && (
          <div
            className="fixed z-50 pointer-events-none px-3 py-2 rounded-lg bg-[#0d1319] border border-[#1e2d3a] shadow-xl text-xs text-[#c8d8e4] whitespace-nowrap"
            style={{ left: tooltip.x + 12, top: tooltip.y - 12 }}
          >
            <div>
              WACC: <span className="text-[#f0f4f0]">{tooltip.wacc.toFixed(1)}%</span>
            </div>
            <div>
              Growth: <span className="text-[#f0f4f0]">{tooltip.growth.toFixed(1)}%</span>
            </div>
            <div className="mt-1 pt-1 border-t border-[#1e2d3a]">
              Upside:{" "}
              <span
                className={`font-semibold ${
                  tooltip.value !== null
                    ? tooltip.value >= 0
                      ? "text-emerald-400"
                      : "text-red-400"
                    : ""
                }`}
              >
                {tooltip.value !== null
                  ? `${tooltip.value >= 0 ? "+" : ""}${tooltip.value.toFixed(1)}%`
                  : "N/A"}
              </span>
            </div>
          </div>
        )}

        {/* Legend */}
        <div className="flex items-center justify-center flex-wrap gap-3 mt-4 text-[10px] text-[#6b7f8e]">
          <span className="flex items-center gap-1">
            <span className="w-3 h-3 rounded-sm inline-block bg-emerald-600" />
            <span>Upside &gt;30%</span>
          </span>
          <span className="flex items-center gap-1">
            <span className="w-3 h-3 rounded-sm inline-block" style={{ backgroundColor: "rgba(16,185,129,0.7)" }} />
            <span>15-30%</span>
          </span>
          <span className="flex items-center gap-1">
            <span className="w-3 h-3 rounded-sm inline-block" style={{ backgroundColor: "rgba(52,211,153,0.5)" }} />
            <span>5-15%</span>
          </span>
          <span className="flex items-center gap-1">
            <span className="w-3 h-3 rounded-sm inline-block" style={{ backgroundColor: "rgba(234,179,8,0.4)" }} />
            <span>-5 to 5%</span>
          </span>
          <span className="flex items-center gap-1">
            <span className="w-3 h-3 rounded-sm inline-block" style={{ backgroundColor: "rgba(249,115,22,0.5)" }} />
            <span>-15 to -5%</span>
          </span>
          <span className="flex items-center gap-1">
            <span className="w-3 h-3 rounded-sm inline-block" style={{ backgroundColor: "rgba(239,68,68,0.6)" }} />
            <span>-30 to -15%</span>
          </span>
          <span className="flex items-center gap-1">
            <span className="w-3 h-3 rounded-sm inline-block bg-red-600" />
            <span>&lt;-30%</span>
          </span>
          <span className="flex items-center gap-1 ml-2">
            <span className="w-3 h-3 rounded-sm inline-block border-2 border-[#84cc16]" />
            <span>Current assumption</span>
          </span>
        </div>
      </CardContent>
    </Card>
  );
}
