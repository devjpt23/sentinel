import { cn } from "@/lib/utils";

function Separator({ className, orientation = "horizontal" }: { className?: string; orientation?: "horizontal" | "vertical" }) {
  return (
    <div
      className={cn(
        "shrink-0 bg-[#1e2d3a]",
        orientation === "horizontal" ? "h-px w-full" : "w-px h-full",
        className
      )}
    />
  );
}

export { Separator };