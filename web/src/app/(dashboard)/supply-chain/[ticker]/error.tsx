"use client";

import { useEffect } from "react";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { AlertTriangle } from "lucide-react";

export default function SupplyChainError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    console.error("Supply chain page error:", error);
  }, [error]);

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold">Supply Chain</h1>
      <Card className="border-red-500/30 bg-red-500/10">
        <CardContent className="pt-6">
          <div className="flex items-center gap-3 mb-3">
            <AlertTriangle className="h-5 w-5 text-red-400" />
            <p className="text-sm font-semibold text-red-400">
              Failed to load supply chain data
            </p>
          </div>
          <p className="text-xs text-[#6b7f8e] mb-4">
            {error.message || "An unexpected error occurred while loading this page."}
          </p>
          <Button variant="outline" size="sm" onClick={reset}>
            Try again
          </Button>
        </CardContent>
      </Card>
    </div>
  );
}
