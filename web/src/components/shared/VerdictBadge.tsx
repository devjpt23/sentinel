"use client";

import { cn, getVerdictInfo } from "@/lib/utils";

interface VerdictBadgeProps {
  verdict: string;
  className?: string;
}

export function VerdictBadge({ verdict, className }: VerdictBadgeProps) {
  const { bg } = getVerdictInfo(verdict);

  return (
    <span className={cn("inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-semibold", bg, className)}>
      {verdict}
    </span>
  );
}