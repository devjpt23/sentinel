"use client";

import * as React from "react";
import { cn } from "@/lib/utils";

interface TabsProps {
  tabs: { id: string; label: string }[];
  activeTab: string;
  onTabChange: (tab: string) => void;
  className?: string;
}

function Tabs({ tabs, activeTab, onTabChange, className }: TabsProps) {
  return (
    <div className={cn("flex gap-1 border-b border-[#1e2d3a]", className)}>
      {tabs.map((tab) => (
        <button
          key={tab.id}
          onClick={() => onTabChange(tab.id)}
          className={cn(
            "px-4 py-2 text-sm font-medium transition-all duration-200 border-b-2 -mb-px",
            activeTab === tab.id
              ? "text-[#84cc16] border-[#84cc16]"
              : "text-[#6b7f8e] border-transparent hover:text-[#c8d8e4] hover:border-[#2a3f52]"
          )}
        >
          {tab.label}
        </button>
      ))}
    </div>
  );
}

export { Tabs };