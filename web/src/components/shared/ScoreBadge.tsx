"use client";

import { cn, getHealthBg, getHealthBarColor } from "@/lib/utils";

interface ScoreBadgeProps {
  score: number;
  size?: "sm" | "md" | "lg";
  showBar?: boolean;
  className?: string;
}

export function ScoreBadge({ score, size = "md", showBar = false, className }: ScoreBadgeProps) {
  const sizes = {
    sm: "text-xs px-1.5 py-0.5",
    md: "text-sm px-2 py-1",
    lg: "text-lg px-3 py-1.5",
  };

  return (
    <div className={cn("inline-flex flex-col items-center gap-1", className)}>
      <span className={cn("font-bold rounded-full border", getHealthBg(score), sizes[size])}>
        {score}
      </span>
      {showBar && (
        <div className="w-full h-1 bg-[#1e2d3a] rounded-full overflow-hidden">
          <div
            className={cn("h-full rounded-full transition-all", getHealthBarColor(score))}
            style={{ width: `${score}%` }}
          />
        </div>
      )}
    </div>
  );
}