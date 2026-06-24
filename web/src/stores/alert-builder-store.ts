import { create } from "zustand";
import type { AlertCondition, AlertRule } from "@/types/api";

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
  moveCondition: (index: number, direction: "up" | "down") => void;
  setLogic: (logic: "AND" | "OR") => void;
  reset: () => void;
  loadRule: (rule: Pick<AlertRule, "name" | "severity" | "scope" | "ticker" | "conditions" | "logic">) => void;
}

const defaultCondition = (): AlertCondition => ({
  signal_category: "",
  signal_id: "",
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
  moveCondition: (index, direction) =>
    set((state) => {
      const conditions = [...state.conditions];
      const target = direction === "up" ? index - 1 : index + 1;
      if (target < 0 || target >= conditions.length) return state;
      [conditions[index], conditions[target]] = [conditions[target], conditions[index]];
      return { conditions };
    }),
  setLogic: (logic) => set({ logic }),
  loadRule: (rule) =>
    set({
      name: rule.name,
      severity: rule.severity as "info" | "warning" | "critical",
      scope: rule.scope as "watchlist" | "single",
      ticker: rule.ticker || "",
      conditions: (typeof rule.conditions === "string"
        ? JSON.parse(rule.conditions)
        : rule.conditions) as AlertCondition[],
      logic: rule.logic as "AND" | "OR",
    }),
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
