import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { OverviewCard } from "@/components/company/OverviewCard";

describe("OverviewCard", () => {
  const defaultProps = {
    ticker: "AAPL",
    healthData: { price: 175, change_pct: 2.5 },
    dcfData: { fair_value_per_share: 150 },
    intrinsicData: {},
    sentiment: {
      analyst: { buy: 12, hold: 8, sell: 3 },
      price_targets: { average: 185 },
      num_analysts: 23,
    },
    institutional: {
      verdict: "Accumulating",
      holders: [{ name: "Vanguard" }, { name: "BlackRock" }],
    },
    insider: {
      insider: [
        { transaction: "Purchase", shares: 5000, value: 800000 },
      ],
    },
    priceGrowth: { growth_3m: 8, growth_6m: 12, growth_12m: 15 },
    macro: {
      vix: { verdict: "Normal" },
      sp500: { verdict: "Uptrend" },
    },
    indices: [],
    isLoading: false,
  };

  it("renders the overview heading", () => {
    render(<OverviewCard {...defaultProps} />);
    expect(screen.getByText("Overview")).toBeInTheDocument();
  });

  it("renders all 6 signal titles", () => {
    render(<OverviewCard {...defaultProps} />);
    expect(screen.getByText("Valuation")).toBeInTheDocument();
    expect(screen.getByText("Wall Street")).toBeInTheDocument();
    expect(screen.getByText("Insiders")).toBeInTheDocument();
    expect(screen.getByText("Smart Money")).toBeInTheDocument();
    expect(screen.getByText("Momentum")).toBeInTheDocument();
    expect(screen.getByText("Regime")).toBeInTheDocument();
  });

  it("shows expensive verdict when price is well above fair value", () => {
    render(<OverviewCard {...defaultProps} dcfData={{ fair_value_per_share: 100 }} />);
    expect(screen.getByText("Expensive")).toBeInTheDocument();
  });

  it("shows cheap verdict when price is below fair value", () => {
    render(<OverviewCard {...defaultProps} dcfData={{ fair_value_per_share: 250 }} />);
    expect(screen.getByText("Cheap")).toBeInTheDocument();
  });

  it("shows fair verdict when price is near fair value", () => {
    render(<OverviewCard {...defaultProps} dcfData={{ fair_value_per_share: 165 }} />);
    expect(screen.getByText("Fair")).toBeInTheDocument();
  });

  it("shows bullish when analysts favor buying", () => {
    render(<OverviewCard {...defaultProps} sentiment={{
      analyst: { buy: 15, hold: 3, sell: 1 },
      price_targets: { average: 200 },
      num_analysts: 19,
    }} />);
    expect(screen.getByText("Bullish")).toBeInTheDocument();
  });

  it("shows bearish when analysts favor selling", () => {
    render(<OverviewCard {...defaultProps} sentiment={{
      analyst: { buy: 2, hold: 5, sell: 10 },
      price_targets: { average: 140 },
      num_analysts: 17,
    }} />);
    expect(screen.getByText("Bearish")).toBeInTheDocument();
  });

  it("shows mixed when analysts are split", () => {
    render(<OverviewCard {...defaultProps} sentiment={{
      analyst: { buy: 5, hold: 10, sell: 5 },
      price_targets: { average: 170 },
      num_analysts: 20,
    }} />);
    expect(screen.getByText("Mixed")).toBeInTheDocument();
  });

  it("shows Buying when insiders are net buyers", () => {
    render(<OverviewCard {...defaultProps} insider={{
      insider: [
        { transaction: "Purchase", shares: 10000, value: 1500000 },
      ],
    }} />);
    expect(screen.getByText("Buying")).toBeInTheDocument();
  });

  it("shows Selling when insiders are net sellers", () => {
    render(<OverviewCard {...defaultProps} insider={{
      insider: [
        { transaction: "Sale", shares: 10000, value: 1500000 },
      ],
    }} />);
    expect(screen.getByText("Selling")).toBeInTheDocument();
  });

  it("shows No data when insider array is empty", () => {
    render(<OverviewCard {...defaultProps} insider={{ insider: [] }} />);
    expect(screen.getByText("Insiders")).toBeInTheDocument();
    // Should show the dash for no-data state
    expect(screen.getByText("No recent insider activity")).toBeInTheDocument();
  });

  it("shows Bullish regime when VIX is calm and S&P is uptrend", () => {
    render(<OverviewCard {...defaultProps} macro={{
      vix: { verdict: "Calm" },
      sp500: { verdict: "Uptrend" },
      yieldCurve: { verdict: "Normal" },
    }} />);
    // "Bullish" may appear in multiple places (e.g. Wall Street + Regime)
    const bullishEls = screen.getAllByText("Bullish");
    expect(bullishEls.length).toBeGreaterThanOrEqual(1);
  });

  it("shows Bearish regime when VIX is fearful", () => {
    render(<OverviewCard {...defaultProps} macro={{
      vix: { verdict: "Fearful" },
      sp500: { verdict: "Uptrend" },
    }} />);
    expect(screen.getByText("Bearish")).toBeInTheDocument();
  });

  it("shows Neutral regime for mixed signals", () => {
    render(<OverviewCard {...defaultProps} macro={{
      vix: { verdict: "Normal" },
      sp500: { verdict: "Choppy" },
    }} />);
    expect(screen.getByText("Neutral")).toBeInTheDocument();
  });

  it("shows loading skeletons when isLoading is true", () => {
    render(<OverviewCard {...defaultProps} isLoading={true} />);
    expect(screen.getByText("Loading analysis…")).toBeInTheDocument();
  });

  it("shows summary line with plain English description", () => {
    render(<OverviewCard {...defaultProps} />);
    // Summary line contains the ticker — look for any paragraph with AAPL
    const paragraphs = screen.getAllByText(/AAPL/);
    expect(paragraphs.length).toBeGreaterThan(0);
  });

  it("handles missing price data gracefully — shows dash for valuation", () => {
    render(<OverviewCard {...defaultProps} healthData={{}} dcfData={{}} />);
    // No-data cards show a dash (—) as the verdict
    const dashes = screen.getAllByText("—");
    expect(dashes.length).toBeGreaterThan(0);
  });

  it("handles missing sentiment data gracefully — shows dash and detail", () => {
    render(<OverviewCard {...defaultProps} sentiment={undefined} />);
    // No-data cards show a dash (—) for the verdict and the detail text below
    const dashes = screen.getAllByText("—");
    expect(dashes.length).toBeGreaterThan(0);
    expect(screen.getByText("No analyst coverage")).toBeInTheDocument();
  });

  it("handles missing macro data gracefully — shows dash and detail", () => {
    render(<OverviewCard {...defaultProps} macro={undefined} />);
    // No-data cards show a dash (—) for the verdict and the detail text below
    const dashes = screen.getAllByText("—");
    expect(dashes.length).toBeGreaterThan(0);
    expect(screen.getByText("No macro data")).toBeInTheDocument();
  });

  it("shows strong momentum when all periods are positive", () => {
    render(<OverviewCard {...defaultProps} priceGrowth={{
      growth_3m: 5,
      growth_6m: 10,
      growth_12m: 20,
    }} />);
    expect(screen.getByText("Strong")).toBeInTheDocument();
  });

  it("shows weak momentum when all periods are negative", () => {
    render(<OverviewCard {...defaultProps} priceGrowth={{
      growth_3m: -5,
      growth_6m: -10,
      growth_12m: -20,
    }} />);
    expect(screen.getByText("Weak")).toBeInTheDocument();
  });
});
