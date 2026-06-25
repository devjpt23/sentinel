import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api-client";
import type { CompareItem } from "@/types/api";

export function useCompare(tickers: string[]) {
  return useQuery({
    queryKey: ["compare", tickers],
    queryFn: async () => {
      const data = await api.compareTickers(tickers);
      return (data.tickers ?? []).filter((t) => !t.error) as CompareItem[];
    },
    enabled: tickers.length >= 2,
    staleTime: 60_000,
    retry: 1,
  });
}
