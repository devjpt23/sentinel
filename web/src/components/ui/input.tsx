import * as React from "react";
import { cn } from "@/lib/utils";

const Input = React.forwardRef<HTMLInputElement, React.InputHTMLAttributes<HTMLInputElement>>(
  ({ className, type, ...props }, ref) => (
    <input
      type={type}
      ref={ref}
      className={cn(
        "flex h-10 w-full rounded-lg border border-[#1e2d3a] bg-[#111922] px-3 py-2 text-sm text-[#f0f4f0] placeholder:text-[#6b7f8e] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#84cc16]/50 disabled:cursor-not-allowed disabled:opacity-50 transition-colors",
        className
      )}
      {...props}
    />
  )
);
Input.displayName = "Input";

export { Input };