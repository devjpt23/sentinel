import { describe, it, expect, beforeEach } from "vitest";
import { useAlertBuilder } from "./alert-builder-store";

describe("alert-builder-store", () => {
  beforeEach(() => {
    useAlertBuilder.getState().reset();
  });

  describe("addCondition", () => {
    it("should add an empty condition", () => {
      const store = useAlertBuilder.getState();
      expect(store.conditions).toHaveLength(1);
      store.addCondition();
      expect(useAlertBuilder.getState().conditions).toHaveLength(2);
    });

    it("new condition should be an empty default", () => {
      useAlertBuilder.getState().addCondition();
      const cond = useAlertBuilder.getState().conditions[1];
      expect(cond.signal_category).toBe("");
      expect(cond.signal_id).toBe("");
      expect(cond.operator).toBe("");
      expect(cond.value).toBe(0);
    });
  });

  describe("removeCondition", () => {
    it("should remove a condition by index", () => {
      const store = useAlertBuilder.getState();
      store.addCondition();
      store.addCondition();
      expect(useAlertBuilder.getState().conditions).toHaveLength(3);
      store.removeCondition(1);
      expect(useAlertBuilder.getState().conditions).toHaveLength(2);
    });
  });

  describe("updateCondition", () => {
    it("should update a field on a condition", () => {
      useAlertBuilder.getState().updateCondition(0, "signal_id", "rsi");
      const cond = useAlertBuilder.getState().conditions[0];
      expect(cond.signal_id).toBe("rsi");
    });

    it("should update a numeric field", () => {
      useAlertBuilder.getState().updateCondition(0, "value", 30);
      const cond = useAlertBuilder.getState().conditions[0];
      expect(cond.value).toBe(30);
    });
  });

  describe("moveCondition", () => {
    it("should swap a condition up", () => {
      const store = useAlertBuilder.getState();
      store.updateCondition(0, "signal_id", "first");
      store.addCondition();
      store.updateCondition(1, "signal_id", "second");
      store.addCondition();
      store.updateCondition(2, "signal_id", "third");

      store.moveCondition(2, "up");
      const conds = useAlertBuilder.getState().conditions;
      expect(conds[1].signal_id).toBe("third");
      expect(conds[2].signal_id).toBe("second");
    });

    it("should swap a condition down", () => {
      const store = useAlertBuilder.getState();
      store.updateCondition(0, "signal_id", "first");
      store.addCondition();
      store.updateCondition(1, "signal_id", "second");
      store.addCondition();
      store.updateCondition(2, "signal_id", "third");

      store.moveCondition(0, "down");
      const conds = useAlertBuilder.getState().conditions;
      expect(conds[0].signal_id).toBe("second");
      expect(conds[1].signal_id).toBe("first");
    });

    it("should not move up from index 0", () => {
      const store = useAlertBuilder.getState();
      store.updateCondition(0, "signal_id", "only");
      store.moveCondition(0, "up");
      expect(useAlertBuilder.getState().conditions[0].signal_id).toBe("only");
    });

    it("should not move down from last index", () => {
      const store = useAlertBuilder.getState();
      store.updateCondition(0, "signal_id", "only");
      store.addCondition();
      store.moveCondition(1, "down");
      expect(useAlertBuilder.getState().conditions[1].signal_id).toBe("");
    });
  });

  describe("setLogic", () => {
    it("should set logic to AND", () => {
      useAlertBuilder.getState().setLogic("AND");
      expect(useAlertBuilder.getState().logic).toBe("AND");
    });

    it("should set logic to OR", () => {
      useAlertBuilder.getState().setLogic("OR");
      expect(useAlertBuilder.getState().logic).toBe("OR");
    });
  });

  describe("setSeverity", () => {
    it("should set severity", () => {
      useAlertBuilder.getState().setSeverity("critical");
      expect(useAlertBuilder.getState().severity).toBe("critical");
    });
  });

  describe("setScope", () => {
    it("should set scope", () => {
      useAlertBuilder.getState().setScope("single");
      expect(useAlertBuilder.getState().scope).toBe("single");
    });
  });

  describe("setTicker", () => {
    it("should set ticker", () => {
      useAlertBuilder.getState().setTicker("AAPL");
      expect(useAlertBuilder.getState().ticker).toBe("AAPL");
    });
  });

  describe("setName", () => {
    it("should set rule name", () => {
      useAlertBuilder.getState().setName("My Rule");
      expect(useAlertBuilder.getState().name).toBe("My Rule");
    });
  });

  describe("loadRule", () => {
    it("should populate store from an existing rule", () => {
      useAlertBuilder.getState().loadRule({
        name: "Price Alert",
        severity: "warning",
        scope: "single",
        ticker: "AAPL",
        conditions: [
          { signal_category: "Price & Volume", signal_id: "price", operator: ">", value: 150 },
        ],
        logic: "AND",
      });

      const state = useAlertBuilder.getState();
      expect(state.name).toBe("Price Alert");
      expect(state.severity).toBe("warning");
      expect(state.scope).toBe("single");
      expect(state.ticker).toBe("AAPL");
      expect(state.conditions).toHaveLength(1);
      expect(state.conditions[0].signal_id).toBe("price");
      expect(state.logic).toBe("AND");
    });

    it("should handle rule with string conditions (JSON)", () => {
      useAlertBuilder.getState().loadRule({
        name: "Test",
        severity: "info",
        scope: "watchlist",
        conditions: JSON.stringify([
          { signal_category: "Technical", signal_id: "rsi", operator: "<", value: 30 },
        ]),
        logic: "AND",
      });

      const state = useAlertBuilder.getState();
      expect(state.conditions).toHaveLength(1);
      expect(state.conditions[0].signal_id).toBe("rsi");
    });

    it("should handle rule with empty ticker", () => {
      useAlertBuilder.getState().loadRule({
        name: "Watchlist Rule",
        severity: "info",
        scope: "watchlist",
        ticker: undefined as unknown as string,
        conditions: [],
        logic: "AND",
      });

      expect(useAlertBuilder.getState().ticker).toBe("");
    });
  });

  describe("reset", () => {
    it("should reset to default state", () => {
      const store = useAlertBuilder.getState();
      store.setName("Custom");
      store.setSeverity("critical");
      store.setScope("single");
      store.setTicker("TSLA");
      store.addCondition();
      store.setLogic("OR");
      store.reset();

      const state = useAlertBuilder.getState();
      expect(state.name).toBe("");
      expect(state.severity).toBe("info");
      expect(state.scope).toBe("watchlist");
      expect(state.ticker).toBe("");
      expect(state.conditions).toHaveLength(1);
      expect(state.conditions[0].signal_id).toBe("");
      expect(state.logic).toBe("AND");
    });
  });
});
