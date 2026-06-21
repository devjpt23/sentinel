import * as React from "react";
import { cn } from "@/lib/utils";

export interface TextareaProps extends React.TextareaHTMLAttributes<HTMLTextAreaElement> {}

const Textarea = React.forwardRef<HTMLTextAreaElement, TextareaProps>(
  ({ className, ...props }, ref) => {
    return (
      <textarea
        className={cn(
          "flex min-h-[60px] w-full rounded-lg border border-[#1e2d3a] bg-[#111922] px-3 py-2 text-sm shadow-sm placeholder:text-[#6b7f8e] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#84cc16]/50 disabled:cursor-not-allowed disabled:opacity-50 text-[#f0f4f0]",
          className
        )}
        ref={ref}
        {...props}
      />
    );
  }
);
Textarea.displayName = "Textarea";

export { Textarea };