import { create } from "zustand";
import { persist } from "zustand/middleware";

const ALL_METRICS = [
  "price",
  "market_cap",
  "pe_ratio",
  "health_score",
  "risk_score",
  "fscore",
  "zscore",
  "growth_3m",
  "growth_6m",
  "growth_12m",
  "fair_value",
  "upside_pct",
];

export interface CompareState {
  tickers: string[];
  addTicker: (ticker: string) => void;
  removeTicker: (ticker: string) => void;
  setTickers: (tickers: string[]) => void;
  clearAll: () => void;

  suggestedPeers: string[];
  setSuggestedPeers: (peers: string[]) => void;
  clearSuggestedPeers: () => void;

  visibleMetrics: string[];
  setVisibleMetrics: (metrics: string[]) => void;

  comparisonHistory: Array<{ tickers: string[]; timestamp: number }>;
  addComparison: (tickers: string[]) => void;
}

const MAX_TICKERS = 10;

export const useCompareStore = create<CompareState>()(
  persist(
    (set, get) => ({
      tickers: [],
      addTicker: (ticker: string) => {
        const upper = ticker.toUpperCase().trim();
        if (!upper) return;
        const current = get().tickers;
        if (current.length >= MAX_TICKERS) return;
        if (current.includes(upper)) return;
        set({ tickers: [...current, upper] });
      },
      removeTicker: (ticker: string) => {
        const upper = ticker.toUpperCase();
        set((state) => ({
          tickers: state.tickers.filter((t) => t !== upper),
        }));
      },
      setTickers: (tickers: string[]) => {
        const cleaned = tickers
          .map((t) => t.toUpperCase().trim())
          .filter((t) => t.length > 0)
          .slice(0, MAX_TICKERS);
        set({ tickers: cleaned });
      },
      clearAll: () => set({ tickers: [] }),

      // Phase 3: suggested peers
      suggestedPeers: [],
      setSuggestedPeers: (peers: string[]) => set({ suggestedPeers: peers }),
      clearSuggestedPeers: () => set({ suggestedPeers: [] }),

      // Phase 4: visible metrics (default: all)
      visibleMetrics: ALL_METRICS,
      setVisibleMetrics: (metrics: string[]) => set({ visibleMetrics: metrics }),

      // Phase 4: comparison history (persisted)
      comparisonHistory: [],
      addComparison: (tickers: string[]) => {
        const MAX_HISTORY = 5;
        const entry = { tickers, timestamp: Date.now() };
        const existing = get().comparisonHistory;
        // Don't add if identical to most recent
        const last = existing[0];
        if (
          last &&
          last.tickers.length === tickers.length &&
          last.tickers.every((t, i) => t === tickers[i])
        ) {
          return;
        }
        set({
          comparisonHistory: [entry, ...existing].slice(0, MAX_HISTORY),
        });
      },
    }),
    {
      name: "sentinel-compare-history",
      partialize: (state) => ({
        comparisonHistory: state.comparisonHistory,
        visibleMetrics: state.visibleMetrics,
      }),
    }
  )
);
