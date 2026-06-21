"use client";

import * as React from "react";
import { cn } from "@/lib/utils";
import { Check } from "lucide-react";

interface CheckboxProps extends Omit<React.InputHTMLAttributes<HTMLInputElement>, "type"> {
  checked?: boolean;
  onCheckedChange?: (checked: boolean) => void;
}

const Checkbox = React.forwardRef<HTMLInputElement, CheckboxProps>(
  ({ className, checked, onCheckedChange, ...props }, ref) => {
    return (
      <label className="inline-flex items-center gap-2 cursor-pointer">
        <div className="relative">
          <input
            ref={ref}
            type="checkbox"
            className="sr-only"
            checked={checked}
            onChange={(e) => onCheckedChange?.(e.target.checked)}
            {...props}
          />
          <div className={cn(
            "w-4 h-4 rounded-md border border-[#1e2d3a] flex items-center justify-center transition-colors",
            checked ? "bg-[#84cc16] border-[#84cc16]" : "bg-[#111922]"
          )}>
            {checked && <Check className="w-3 h-3 text-[#0a0e13]" />}
          </div>
        </div>
      </label>
    );
  }
);
Checkbox.displayName = "Checkbox";

export { Checkbox };