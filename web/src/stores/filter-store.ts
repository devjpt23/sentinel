import { create } from "zustand";

interface FilterState {
  sector: string;
  country: string;
  minMarketCap: number;
  maxMarketCap: number;
  minScore: number;
  sortBy: string;
  sortOrder: "asc" | "desc";
  setSector: (sector: string) => void;
  setCountry: (country: string) => void;
  setMinMarketCap: (value: number) => void;
  setMaxMarketCap: (value: number) => void;
  setMinScore: (value: number) => void;
  setSortBy: (field: string) => void;
  setSortOrder: (order: "asc" | "desc") => void;
  reset: () => void;
}

const DEFAULTS = {
  sector: "",
  country: "",
  minMarketCap: 0,
  maxMarketCap: 1e15,
  minScore: 0,
  sortBy: "marketCap",
  sortOrder: "desc" as const,
};

export const useFilterStore = create<FilterState>()((set) => ({
  ...DEFAULTS,
  setSector: (sector) => set({ sector }),
  setCountry: (country) => set({ country }),
  setMinMarketCap: (minMarketCap) => set({ minMarketCap }),
  setMaxMarketCap: (maxMarketCap) => set({ maxMarketCap }),
  setMinScore: (minScore) => set({ minScore }),
  setSortBy: (sortBy) => set({ sortBy }),
  setSortOrder: (sortOrder) => set({ sortOrder }),
  reset: () => set(DEFAULTS),
}));
