import { describe, it, expect } from "vitest";
import {
  getSignalColor,
  getSignalBg,
  computeRegime,
} from "@/lib/utils";

describe("getSignalColor", () => {
  it("returns green for positive verdicts", () => {
    expect(getSignalColor("Cheap")).toBe("text-emerald-400");
    expect(getSignalColor("Bullish")).toBe("text-emerald-400");
    expect(getSignalColor("Buying")).toBe("text-emerald-400");
    expect(getSignalColor("Strong")).toBe("text-emerald-400");
    expect(getSignalColor("Uptrend")).toBe("text-emerald-400");
    expect(getSignalColor("Calm")).toBe("text-emerald-400");
  });

  it("returns red for negative verdicts", () => {
    expect(getSignalColor("Expensive")).toBe("text-red-400");
    expect(getSignalColor("Bearish")).toBe("text-red-400");
    expect(getSignalColor("Selling")).toBe("text-red-400");
    expect(getSignalColor("Weak")).toBe("text-red-400");
    expect(getSignalColor("Downtrend")).toBe("text-red-400");
    expect(getSignalColor("Fearful")).toBe("text-red-400");
  });

  it("returns yellow for neutral verdicts", () => {
    expect(getSignalColor("Fair")).toBe("text-yellow-400");
    expect(getSignalColor("Mixed")).toBe("text-yellow-400");
    expect(getSignalColor("Neutral")).toBe("text-yellow-400");
    expect(getSignalColor("N/A")).toBe("text-yellow-400");
  });

  it("is case-insensitive", () => {
    expect(getSignalColor("cheap")).toBe("text-emerald-400");
    expect(getSignalColor("EXPENSIVE")).toBe("text-red-400");
    expect(getSignalColor("Fair")).toBe("text-yellow-400");
  });
});

describe("getSignalBg", () => {
  it("returns green background for positive verdicts", () => {
    expect(getSignalBg("Cheap")).toBe("bg-emerald-500/20 border-emerald-500/30");
    expect(getSignalBg("Bullish")).toBe("bg-emerald-500/20 border-emerald-500/30");
  });

  it("returns red background for negative verdicts", () => {
    expect(getSignalBg("Expensive")).toBe("bg-red-500/20 border-red-500/30");
    expect(getSignalBg("Selling")).toBe("bg-red-500/20 border-red-500/30");
  });

  it("returns yellow background for neutral verdicts", () => {
    expect(getSignalBg("Fair")).toBe("bg-yellow-500/20 border-yellow-500/30");
    expect(getSignalBg("N/A")).toBe("bg-yellow-500/20 border-yellow-500/30");
  });
});

describe("computeRegime", () => {
  it("returns Bullish when all indicators are positive", () => {
    const result = computeRegime(
      {
        vix: { verdict: "Calm" },
        sp500: { verdict: "Uptrend" },
        yieldCurve: { verdict: "Normal" },
      },
      undefined,
    );
    expect(result.verdict).toBe("Bullish");
    expect(result.vixVerdict).toBe("Calm");
    expect(result.spTrend).toBe("Uptrend");
  });

  it("returns Bearish when VIX is fearful", () => {
    const result = computeRegime(
      { vix: { verdict: "Fearful" }, sp500: { verdict: "Uptrend" } },
      undefined,
    );
    expect(result.verdict).toBe("Bearish");
  });

  it("returns Bearish when S&P is in downtrend", () => {
    const result = computeRegime(
      { vix: { verdict: "Calm" }, sp500: { verdict: "Downtrend" } },
      undefined,
    );
    expect(result.verdict).toBe("Bearish");
  });

  it("returns Bearish when yield curve is inverted", () => {
    const result = computeRegime(
      {
        vix: { verdict: "Calm" },
        sp500: { verdict: "Uptrend" },
        yieldCurve: { verdict: "Inverted" },
      },
      undefined,
    );
    expect(result.verdict).toBe("Bearish");
  });

  it("returns Neutral for mixed signals", () => {
    const result = computeRegime(
      { vix: { verdict: "Normal" }, sp500: { verdict: "Choppy" } },
      undefined,
    );
    expect(result.verdict).toBe("Neutral");
  });

  it("returns Unknown when no data is available", () => {
    const result = computeRegime(undefined, undefined);
    expect(result.verdict).toBe("Unknown");
  });

  it("returns Unknown when macro data is empty", () => {
    const result = computeRegime({}, undefined);
    expect(result.verdict).toBe("Unknown");
  });

  it("passes through component details even when regime is neutral", () => {
    const result = computeRegime(
      { vix: { verdict: "Normal" }, sp500: { verdict: "Choppy" } },
      undefined,
    );
    expect(result.vixVerdict).toBe("Normal");
    expect(result.spTrend).toBe("Choppy");
  });
});
