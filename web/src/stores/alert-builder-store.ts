import { create } from "zustand";
import type { AlertCondition } from "@/types/api";

interface AlertBuilderState {
  name: string;
  severity: "info" | "warning" | "critical";
  scope: "watchlist" | "single";
  ticker: string;
  conditions: AlertCondition[];
  logic: "AND" | "OR";
  setName: (name: string) => void;
  setSeverity: (severity: "info" | "warning" | "critical") => void;
  setScope: (scope: "watchlist" | "single") => void;
  setTicker: (ticker: string) => void;
  addCondition: () => void;
  updateCondition: (index: number, field: keyof AlertCondition, value: string | number) => void;
  removeCondition: (index: number) => void;
  setLogic: (logic: "AND" | "OR") => void;
  reset: () => void;
}

const defaultCondition = (): AlertCondition => ({
  signal_category: "",
  signal: "",
  operator: "",
  value: 0,
  days: undefined,
  period: undefined,
});

export const useAlertBuilder = create<AlertBuilderState>((set) => ({
  name: "",
  severity: "info",
  scope: "watchlist",
  ticker: "",
  conditions: [defaultCondition()],
  logic: "AND",
  setName: (name) => set({ name }),
  setSeverity: (severity) => set({ severity }),
  setScope: (scope) => set({ scope }),
  setTicker: (ticker) => set({ ticker }),
  addCondition: () =>
    set((state) => ({
      conditions: [...state.conditions, defaultCondition()],
    })),
  updateCondition: (index, field, value) =>
    set((state) => ({
      conditions: state.conditions.map((c, i) =>
        i === index ? { ...c, [field]: value } : c
      ),
    })),
  removeCondition: (index) =>
    set((state) => ({
      conditions: state.conditions.filter((_, i) => i !== index),
    })),
  setLogic: (logic) => set({ logic }),
  reset: () =>
    set({
      name: "",
      severity: "info",
      scope: "watchlist",
      ticker: "",
      conditions: [defaultCondition()],
      logic: "AND",
    }),
}));
