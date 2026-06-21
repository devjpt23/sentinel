import * as React from "react";
import { cn } from "@/lib/utils";

interface BadgeProps extends React.HTMLAttributes<HTMLSpanElement> {
  variant?: "default" | "success" | "warning" | "danger" | "outline" | "secondary" | "primary";
}

const Badge = React.forwardRef<HTMLSpanElement, BadgeProps>(
  ({ className, variant = "default", ...props }, ref) => {
    const variants = {
      primary: "bg-[#84cc16]/20 text-[#84cc16] border border-[#84cc16]/30",
      default: "bg-[#1a2a38] text-[#c8d8e4]",
      success: "bg-emerald-500/20 text-emerald-400 border border-emerald-500/30",
      warning: "bg-yellow-500/20 text-yellow-400 border border-yellow-500/30",
      danger: "bg-red-500/20 text-red-400 border border-red-500/30",
      outline: "border border-[#1e2d3a] text-[#c8d8e4]",
      secondary: "bg-[#1a2a38] text-[#6b7f8e] border border-[#1e2d3a]",
    };

    return (
      <span
        ref={ref}
        className={cn("inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-semibold transition-colors", variants[variant], className)}
        {...props}
      />
    );
  }
);
Badge.displayName = "Badge";

export { Badge };
