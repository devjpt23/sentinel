import * as React from "react";
import { cn } from "@/lib/utils";

interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: "default" | "destructive" | "outline" | "secondary" | "ghost" | "primary";
  size?: "default" | "sm" | "lg" | "icon";
}

const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant = "default", size = "default", ...props }, ref) => {
    const variants = {
      primary: "bg-[#84cc16] text-[#0a0e13] hover:bg-[#65a30d] shadow-lg shadow-[#84cc16]/20 font-semibold",
      default: "bg-[#f0f4f0] text-[#0a0e13] hover:bg-[#d8e0d8]",
      destructive: "bg-red-600 text-white hover:bg-red-700",
      outline: "border border-[#1e2d3a] bg-transparent hover:bg-[#1a2a38] text-[#f0f4f0]",
      secondary: "bg-[#1a2a38] text-[#c8d8e4] hover:bg-[#243545]",
      ghost: "hover:bg-[#1a2a38] text-[#c8d8e4]",
    };
    const sizes = {
      default: "h-10 px-4 py-2",
      sm: "h-8 rounded-md px-3 text-xs",
      lg: "h-12 rounded-lg px-8",
      icon: "h-9 w-9",
    };

    return (
      <button
        ref={ref}
        className={cn(
          "inline-flex items-center justify-center rounded-lg text-sm font-medium transition-all duration-200 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#84cc16]/50 disabled:pointer-events-none disabled:opacity-50",
          variants[variant],
          sizes[size],
          className
        )}
        {...props}
      />
    );
  }
);
Button.displayName = "Button";

export { Button };
