import { create } from "zustand";
import { persist } from "zustand/middleware";

interface WatchlistState {
  tickers: string[];
  addTicker: (ticker: string) => void;
  removeTicker: (ticker: string) => void;
  clearWatchlist: () => void;
  hasTicker: (ticker: string) => boolean;

  // Phase 4: compare selection
  selectedForCompare: string[];
  toggleCompareSelection: (ticker: string) => void;
  clearCompareSelection: () => void;
}

export const useWatchlistStore = create<WatchlistState>()(
  persist(
    (set, get) => ({
      tickers: [],
      addTicker: (ticker: string) => {
        const upper = ticker.toUpperCase();
        set((state) => ({
          tickers: state.tickers.includes(upper)
            ? state.tickers
            : [...state.tickers, upper],
        }));
      },
      removeTicker: (ticker: string) => {
        const upper = ticker.toUpperCase();
        set((state) => ({
          tickers: state.tickers.filter((t) => t !== upper),
        }));
      },
      clearWatchlist: () => set({ tickers: [] }),
      hasTicker: (ticker: string) =>
        get().tickers.includes(ticker.toUpperCase()),

      // Phase 4: compare selection
      selectedForCompare: [],
      toggleCompareSelection: (ticker: string) => {
        const upper = ticker.toUpperCase();
        set((state) => ({
          selectedForCompare: state.selectedForCompare.includes(upper)
            ? state.selectedForCompare.filter((t) => t !== upper)
            : [...state.selectedForCompare, upper],
        }));
      },
      clearCompareSelection: () => set({ selectedForCompare: [] }),
    }),
    {
      name: "sentinel-watchlist",
      partialize: (state) => ({
        tickers: state.tickers,
        selectedForCompare: state.selectedForCompare,
      }),
    }
  )
);
