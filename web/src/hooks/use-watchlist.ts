import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api-client";

// For now we use a placeholder user ID. In production, get this from auth context.
const USER_ID = 1;

export function useWatchlist() {
  return useQuery({
    queryKey: ["watchlist", USER_ID],
    queryFn: async () => {
      const data = await api.getWatchlist(USER_ID);
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

export function useEnrichedWatchlist() {
  return useQuery({
    queryKey: ["watchlist-enriched", USER_ID],
    queryFn: async () => {
      const data = await api.getEnrichedWatchlist(USER_ID);
      return data.items ?? [];
    },
    refetchInterval: 60_000, // slower, more expensive endpoint
  });
}

export function useAddToWatchlist() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (ticker: string) => api.addToWatchlist(USER_ID, ticker),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["watchlist", USER_ID] });
    },
  });
}

export function useRemoveFromWatchlist() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (ticker: string) => api.removeFromWatchlist(USER_ID, ticker),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["watchlist", USER_ID] });
    },
  });
}

export function usePreferences() {
  return useQuery({
    queryKey: ["preferences", USER_ID],
    queryFn: () => api.getPreferences(USER_ID),
    staleTime: 60_000,
  });
}

export function useUpdatePreferences() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (prefs: Record<string, unknown>) => api.setPreferences(USER_ID, prefs),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["preferences", USER_ID] });
    },
  });
}

export function useUser() {
  return useQuery({
    queryKey: ["user", "me"],
    queryFn: () => api.getMe(),
    staleTime: Infinity,
    refetchOnWindowFocus: false,
  });
}
