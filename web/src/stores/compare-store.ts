import { create } from "zustand";

export interface CompareState {
  tickers: string[];
  addTicker: (ticker: string) => void;
  removeTicker: (ticker: string) => void;
  setTickers: (tickers: string[]) => void;
  clearAll: () => void;
}

const MAX_TICKERS = 10;

export const useCompareStore = create<CompareState>()((set, get) => ({
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
}));
