import { cn } from "@/lib/utils";

function Skeleton({ className, ...props }: React.HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      className={cn("animate-pulse rounded-lg bg-[#1e2d3a]", className)}
      {...props}
    />
  );
}

export { Skeleton };