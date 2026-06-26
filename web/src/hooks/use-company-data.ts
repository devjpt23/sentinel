import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api-client";

export function useHealth(ticker: string) {
  return useQuery({
    queryKey: ["company", ticker, "health"],
    queryFn: () => api.getHealth(ticker),
    staleTime: 5 * 60_000,
    enabled: !!ticker,
  });
}

export function useIntrinsic(ticker: string) {
  return useQuery({
    queryKey: ["company", ticker, "intrinsic"],
    queryFn: () => api.getIntrinsic(ticker),
    staleTime: 5 * 60_000,
    enabled: !!ticker,
  });
}

export function useRisk(ticker: string) {
  return useQuery({
    queryKey: ["company", ticker, "risk"],
    queryFn: () => api.getRisk(ticker),
    staleTime: 5 * 60_000,
    enabled: !!ticker,
  });
}

export function useFinancials(ticker: string) {
  return useQuery({
    queryKey: ["company", ticker, "financials"],
    queryFn: () => api.getFinancials(ticker),
    staleTime: 10 * 60_000,
    enabled: !!ticker,
  });
}

export function useDcf(ticker: string, params?: {
  revenue_growth_5yr?: number;
  terminal_growth?: number;
  discount_rate?: number;
  margin_improvement?: number;
}) {
  return useQuery({
    queryKey: ["company", ticker, "dcf", params],
    queryFn: () => api.getDcf(ticker, params),
    staleTime: 5 * 60_000,
    enabled: !!ticker,
  });
}

export function usePriceGrowth(ticker: string) {
  return useQuery({
    queryKey: ["company", ticker, "price-growth"],
    queryFn: () => api.getPriceGrowth(ticker),
    staleTime: 5 * 60_000,
    enabled: !!ticker,
  });
}

export function usePriceHistory(ticker: string, period = "1y") {
  return useQuery({
    queryKey: ["company", ticker, "price-history", period],
    queryFn: () => api.getPriceHistory(ticker, period),
    staleTime: 60_000, // price data stale after 1 min
    enabled: !!ticker,
  });
}

export function usePeers(ticker: string) {
  return useQuery({
    queryKey: ["company", ticker, "peers"],
    queryFn: () => api.getPeers(ticker),
    staleTime: 10 * 60_000,
    enabled: !!ticker,
  });
}

export function useSentiment(ticker: string) {
  return useQuery({
    queryKey: ["company", ticker, "sentiment"],
    queryFn: () => api.getSentiment(ticker),
    staleTime: 10 * 60_000,
    enabled: !!ticker,
  });
}

export function useInstitutional(ticker: string) {
  return useQuery({
    queryKey: ["company", ticker, "institutional"],
    queryFn: () => api.getInstitutional(ticker),
    staleTime: 10 * 60_000,
    enabled: !!ticker,
  });
}

export function useInsider(ticker: string) {
  return useQuery({
    queryKey: ["company", ticker, "insider"],
    queryFn: () => api.getInsider(ticker),
    staleTime: 10 * 60_000,
    enabled: !!ticker,
  });
}

export function useMacro() {
  return useQuery({
    queryKey: ["market", "macro"],
    queryFn: () => api.getMacro(),
    staleTime: 10 * 60_000, // market-wide data changes slowly
    enabled: true,
  });
}

export function useIndices() {
  return useQuery({
    queryKey: ["market", "indices"],
    queryFn: () => api.getIndices(),
    staleTime: 5 * 60_000,
    enabled: true,
  });
}

export function useOptions(ticker: string) {
  return useQuery({
    queryKey: ["company", ticker, "options"],
    queryFn: () => api.getOptions(ticker),
    staleTime: 60_000, // options data changes fast
    enabled: !!ticker,
  });
}
