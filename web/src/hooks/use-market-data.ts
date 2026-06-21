import { useQuery, useQueries } from "@tanstack/react-query";
import { api, type Mover } from "@/lib/api-client";

export function useMarketIndices() {
  return useQuery({
    queryKey: ["market", "indices"],
    queryFn: async () => {
      const data = await api.getIndices();
      return data.indices ?? [];
    },
    staleTime: 60_000,
  });
}

export function useMacroIndicators() {
  return useQuery({
    queryKey: ["market", "macro"],
    queryFn: async () => {
      const data = await api.getMacro();
      return data ?? {};
    },
    staleTime: 60_000,
  });
}

export function useMarketNews(limit = 5) {
  return useQuery({
    queryKey: ["market", "news", limit],
    queryFn: async () => {
      const data = await api.getNews(limit);
      return data.news ?? [];
    },
    staleTime: 5 * 60_000,
  });
}

// Market movers — 5 min stale time to avoid hitting yfinance rate limits
export function useMarketMovers() {
  return useQuery({
    queryKey: ["market", "movers"],
    queryFn: async () => {
      const data = await api.getMovers(10);
      return { gainers: data.gainers ?? [], losers: data.losers ?? [] };
    },
    staleTime: 5 * 60_000,
  });
}
