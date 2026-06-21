import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api-client";

export function usePrices(ticker: string, enabled = true) {
  return useQuery({
    queryKey: ["prices", ticker],
    queryFn: async () => {
      const [health, priceGrowth] = await Promise.all([
        api.get<Record<string, unknown>>("/api/data/" + ticker + "/health"),
        api.get<Record<string, unknown>>("/api/data/" + ticker + "/price-growth"),
      ]);
      return { health, priceGrowth };
    },
    enabled: enabled && !!ticker,
    refetchInterval: 30_000,
    staleTime: 25_000,
  });
}
