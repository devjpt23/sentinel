import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api-client";
import type { SupplyChainResponse } from "@/types/supply-chain";

export function useSupplyChain(ticker: string) {
  return useQuery({
    queryKey: ["supply-chain", ticker],
    queryFn: () => api.get<SupplyChainResponse>(`/api/data/${ticker}/supply-chain`),
    staleTime: 10 * 60_000, // supply chain data changes slowly
    enabled: !!ticker,
  });
}
