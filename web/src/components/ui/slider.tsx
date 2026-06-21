"use client";

import * as React from "react";
import { cn } from "@/lib/utils";

interface SliderProps {
  value: number;
  min: number;
  max: number;
  step?: number;
  onValueChange: (value: number) => void;
  className?: string;
  label?: string;
  formatValue?: (value: number) => string;
}

function Slider({ value, min, max, step = 1, onValueChange, className, label, formatValue }: SliderProps) {
  return (
    <div className={cn("space-y-2", className)}>
      {label && (
        <div className="flex justify-between text-sm">
          <span className="text-[#6b7f8e]">{label}</span>
          <span className="font-mono text-[#f0f4f0]">
            {formatValue ? formatValue(value) : value}
          </span>
        </div>
      )}
      <input
        type="range"
        min={min}
        max={max}
        step={step}
        value={value}
        onChange={(e) => onValueChange(parseFloat(e.target.value))}
        className="w-full h-2 bg-[#1e2d3a] rounded-lg appearance-none cursor-pointer accent-[#84cc16]"
      />
    </div>
  );
}

export { Slider };