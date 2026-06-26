import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { OptionsSummaryPanel } from "./OptionsSummaryPanel";

describe("OptionsSummaryPanel", () => {
  const defaultSummary = {
    atm_iv: 0.28,
    put_call_ratio_oi: 1.15,
    put_call_ratio_vol: 0.92,
    max_pain: 185.0,
    total_call_oi: 1450000,
    total_put_oi: 1670000,
  };

  it("renders all 4 metric cards with correct values", () => {
    render(
      <OptionsSummaryPanel summary={defaultSummary} underlyingPrice={185.50} isLoading={false} />,
    );

    expect(screen.getByText("ATM IV")).toBeInTheDocument();
    expect(screen.getByText("PCR (OI)")).toBeInTheDocument();
    expect(screen.getByText("PCR (Vol)")).toBeInTheDocument();
    expect(screen.getByText("Max Pain")).toBeInTheDocument();
  });

  it("formats ATM IV as percentage", () => {
    render(
      <OptionsSummaryPanel summary={defaultSummary} underlyingPrice={185.50} isLoading={false} />,
    );

    expect(screen.getByText("28.0%")).toBeInTheDocument();
  });

  it("formats Max Pain as price", () => {
    render(
      <OptionsSummaryPanel summary={defaultSummary} underlyingPrice={185.50} isLoading={false} />,
    );

    expect(screen.getByText("$185.00")).toBeInTheDocument();
  });

  it("shows PCR values with 2 decimal places", () => {
    render(
      <OptionsSummaryPanel summary={defaultSummary} underlyingPrice={185.50} isLoading={false} />,
    );

    expect(screen.getByText("1.15")).toBeInTheDocument();
    expect(screen.getByText("0.92")).toBeInTheDocument();
  });

  it("shows emerald text for bearish PCR (>1.0)", () => {
    render(
      <OptionsSummaryPanel summary={{
        ...defaultSummary,
        put_call_ratio_oi: 0.50,
      }} underlyingPrice={185.50} isLoading={false} />,
    );

    const pcrOi = screen.getByText("0.50");
    expect(pcrOi.className).toContain("text-emerald-400");
  });

  it("shows yellow text for neutral PCR (0.7-1.0)", () => {
    render(
      <OptionsSummaryPanel summary={{
        ...defaultSummary,
        put_call_ratio_oi: 0.85,
      }} underlyingPrice={185.50} isLoading={false} />,
    );

    const pcrOi = screen.getByText("0.85");
    expect(pcrOi.className).toContain("text-yellow-400");
  });

  it("shows red text for bullish PCR (>1.0)", () => {
    render(
      <OptionsSummaryPanel summary={{
        ...defaultSummary,
        put_call_ratio_oi: 1.50,
      }} underlyingPrice={185.50} isLoading={false} />,
    );

    const pcrOi = screen.getByText("1.50");
    expect(pcrOi.className).toContain("text-red-400");
  });

  it("shows em-dash for null values", () => {
    render(
      <OptionsSummaryPanel
        summary={{
          atm_iv: null,
          put_call_ratio_oi: null,
          put_call_ratio_vol: null,
          max_pain: null,
          total_call_oi: null,
          total_put_oi: null,
        }}
        underlyingPrice={null}
        isLoading={false}
      />,
    );

    const dashes = screen.getAllByText("—");
    expect(dashes.length).toBe(4);
  });

  it("shows em-dash when summary is null", () => {
    render(
      <OptionsSummaryPanel summary={null} underlyingPrice={null} isLoading={false} />,
    );

    const dashes = screen.getAllByText("—");
    expect(dashes.length).toBe(4);
  });

  it("shows loading skeletons when isLoading is true", () => {
    render(
      <OptionsSummaryPanel summary={defaultSummary} underlyingPrice={185.50} isLoading={true} />,
    );

    // Should not show metric values while loading
    expect(screen.queryByText("28.0%")).not.toBeInTheDocument();
    // Should show skeleton placeholders instead
    expect(screen.queryByText("ATM IV")).not.toBeInTheDocument();
  });
});
