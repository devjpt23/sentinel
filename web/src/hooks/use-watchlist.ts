import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api-client";
import type { User } from "@/types/api";

export function useWatchlist(userId: number) {
  return useQuery({
    queryKey: ["watchlist", userId],
    queryFn: async () => {
      const data = await api.getWatchlist(userId);
      return data.tickers ?? [];
    },
    refetchInterval: 30_000,
  });
}

export interface EnrichedWatchlistItem {
  ticker: string;
  name: string;
  sector: string;
  price: number;
  change: number;
  change_pct: number;
  healthScore: number;
  verdict: string;
  riskLabel: string;
  growth3m: number | null;
  growth6m: number | null;
  growth12m: number | null;
  error?: boolean;
}

export function useEnrichedWatchlist(userId: number) {
  return useQuery({
    queryKey: ["watchlist-enriched", userId],
    queryFn: async () => {
      const data = await api.getEnrichedWatchlist(userId);
      return (data.items ?? []).map(cleanItem);
    },
    refetchInterval: 60_000, // slower, more expensive endpoint
  });
}

// Strip CSS selector prefixes leaked into ticker data (e.g. "@E32 AAPL")
function cleanItem(item: EnrichedWatchlistItem): EnrichedWatchlistItem {
  if (item.ticker && item.ticker.includes("@")) {
    item.ticker = item.ticker.split(" ").filter((p) => !p.startsWith("@")).join(" ").trim();
  }
  return item;
}

export function useAddToWatchlist(userId: number) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (ticker: string) => api.addToWatchlist(userId, ticker),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["watchlist", userId] });
    },
  });
}

export function useRemoveFromWatchlist(userId: number) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (ticker: string) => api.removeFromWatchlist(userId, ticker),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["watchlist", userId] });
    },
  });
}

export function usePreferences(userId: number) {
  return useQuery({
    queryKey: ["preferences", userId],
    queryFn: () => api.getPreferences(userId),
    staleTime: 60_000,
  });
}

export function useUpdatePreferences(userId: number) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (prefs: Record<string, unknown>) => api.setPreferences(userId, prefs),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["preferences", userId] });
    },
  });
}

export function useUser() {
  return useQuery<User | null>({
    queryKey: ["user", "me"],
    queryFn: () => api.getMe() as Promise<User | null>,
    staleTime: Infinity,
    refetchOnWindowFocus: false,
  });
}
