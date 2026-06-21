"use client";

import { cn, getRiskBg } from "@/lib/utils";

interface RiskBadgeProps {
  label: string;
  className?: string;
}

export function RiskBadge({ label, className }: RiskBadgeProps) {
  const bg = getRiskBg(label);

  return (
    <span className={cn("inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-semibold", bg, className)}>
      {label} Risk
    </span>
  );
}
