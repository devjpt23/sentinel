import { create } from "zustand";
import { persist } from "zustand/middleware";

interface WatchlistState {
  tickers: string[];
  addTicker: (ticker: string) => void;
  removeTicker: (ticker: string) => void;
  clearWatchlist: () => void;
  hasTicker: (ticker: string) => boolean;
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
    }),
    {
      name: "sentinel-watchlist",
    }
  )
);
