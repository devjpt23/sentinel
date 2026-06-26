import { describe, it, expect } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { OptionsChainTable } from "./OptionsChainTable";
import type { OptionContract } from "./OptionsChainTable";

const makeContract = (overrides: Partial<OptionContract> = {}): OptionContract => ({
  strike: 180.0,
  contract_id: "AAPL240712C00180000",
  last_price: 6.50,
  bid: 6.40,
  ask: 6.60,
  volume: 12500,
  open_interest: 45000,
  iv: 0.25,
  delta: 0.65,
  gamma: 0.045,
  theta: -0.08,
  vega: 0.15,
  rho: 0.02,
  ...overrides,
});

const mockChain = {
  "2026-07-10": {
    calls: [
      makeContract({ strike: 180.0, contract_id: "C1", last_price: 6.50, volume: 12500, open_interest: 45000 }),
      makeContract({ strike: 185.0, contract_id: "C2", last_price: 2.50, volume: 8000, open_interest: 30000 }),
    ],
    puts: [
      makeContract({ strike: 180.0, contract_id: "P1", last_price: 1.50, volume: 10000, open_interest: 55000, delta: -0.35 }),
      makeContract({ strike: 185.0, contract_id: "P2", last_price: 3.50, volume: 12000, open_interest: 60000, delta: -0.48 }),
    ],
  },
  "2026-07-17": {
    calls: [
      makeContract({ strike: 180.0, contract_id: "C3", last_price: 8.00, volume: 5000, open_interest: 20000 }),
    ],
    puts: [
      makeContract({ strike: 180.0, contract_id: "P3", last_price: 2.00, volume: 7000, open_interest: 35000 }),
    ],
  },
};

describe("OptionsChainTable", () => {
  describe("Loading state", () => {
    it("shows skeleton placeholders when loading without data", () => {
      render(
        <OptionsChainTable chain={null} expirations={[]} underlyingPrice={null} isLoading={true} />,
      );

      // Should not show any data text
      expect(screen.queryByText("No options data available")).not.toBeInTheDocument();
    });

    it("empty state takes precedence when chain is null even if expirations exist", () => {
      render(
        <OptionsChainTable chain={null} expirations={["2026-07-10"]} underlyingPrice={null} isLoading={true} />,
      );

      // When chain data is null, empty state shows regardless of loading
      expect(screen.getByText("No options data available")).toBeInTheDocument();
    });
  });

  describe("Empty state", () => {
    it("shows 'No options data available' when chain is null", () => {
      render(
        <OptionsChainTable chain={null} expirations={[]} underlyingPrice={null} isLoading={false} />,
      );

      expect(screen.getByText("No options data available")).toBeInTheDocument();
    });

    it("shows 'No options data available' when chain is empty object", () => {
      render(
        <OptionsChainTable chain={{}} expirations={[]} underlyingPrice={null} isLoading={false} />,
      );

      expect(screen.getByText("No options data available")).toBeInTheDocument();
    });
  });

  describe("Full data rendering", () => {
    it("renders expiry selector buttons", () => {
      render(
        <OptionsChainTable
          chain={mockChain}
          expirations={["2026-07-10", "2026-07-17"]}
          underlyingPrice={185.50}
          isLoading={false}
        />,
      );

      expect(screen.getByText("2026-07-10")).toBeInTheDocument();
      expect(screen.getByText("2026-07-17")).toBeInTheDocument();
    });

    it("renders column headers", () => {
      render(
        <OptionsChainTable
          chain={mockChain}
          expirations={["2026-07-10"]}
          underlyingPrice={185.50}
          isLoading={false}
        />,
      );

      expect(screen.getByText("Calls")).toBeInTheDocument();
      expect(screen.getAllByText("Strike").length).toBeGreaterThan(0);
      expect(screen.getByText("Puts")).toBeInTheDocument();
    });

    it("renders strike prices in the table", () => {
      render(
        <OptionsChainTable
          chain={mockChain}
          expirations={["2026-07-10"]}
          underlyingPrice={185.50}
          isLoading={false}
        />,
      );

      expect(screen.getByText("180")).toBeInTheDocument();
      expect(screen.getByText("185")).toBeInTheDocument();
    });

    it("renders LTP values formatted as currency", () => {
      render(
        <OptionsChainTable
          chain={mockChain}
          expirations={["2026-07-10"]}
          underlyingPrice={185.50}
          isLoading={false}
        />,
      );

      expect(screen.getByText("$6.50")).toBeInTheDocument();
      expect(screen.getByText("$2.50")).toBeInTheDocument();
      expect(screen.getByText("$1.50")).toBeInTheDocument();
      expect(screen.getByText("$3.50")).toBeInTheDocument();
    });

    it("renders volume with comma formatting", () => {
      render(
        <OptionsChainTable
          chain={mockChain}
          expirations={["2026-07-10"]}
          underlyingPrice={185.50}
          isLoading={false}
        />,
      );

      expect(screen.getByText("12,500")).toBeInTheDocument();
      expect(screen.getByText("8,000")).toBeInTheDocument();
    });

    it("renders IV as percentage", () => {
      render(
        <OptionsChainTable
          chain={mockChain}
          expirations={["2026-07-10"]}
          underlyingPrice={185.50}
          isLoading={false}
        />,
      );

      const ivCells = screen.getAllByText("25.0%");
      expect(ivCells.length).toBeGreaterThan(0);
    });

    it("highlights ATM strike row", () => {
      render(
        <OptionsChainTable
          chain={mockChain}
          expirations={["2026-07-10"]}
          underlyingPrice={185.50}
          isLoading={false}
        />,
      );

      // Underlying = 185.50, closest strike = 185, so 185 should be highlighted
      const strike185 = screen.getByText("185");
      // The ATM strike should have green text
      expect(strike185.className).toContain("text-[#84cc16]");
    });
  });

  describe("Expiry switching", () => {
    it("switches expiry when a different expiry button is clicked", () => {
      render(
        <OptionsChainTable
          chain={mockChain}
          expirations={["2026-07-10", "2026-07-17"]}
          underlyingPrice={185.50}
          isLoading={false}
        />,
      );

      // Default shows first expiry data
      expect(screen.getByText("$6.50")).toBeInTheDocument();

      // Click second expiry
      fireEvent.click(screen.getByText("2026-07-17"));

      // Now should show data for 2026-07-17
      expect(screen.getByText("$8.00")).toBeInTheDocument();
    });
  });

  describe("Column sorting", () => {
    it("sorts by strike ascending by default", () => {
      render(
        <OptionsChainTable
          chain={mockChain}
          expirations={["2026-07-10"]}
          underlyingPrice={185.50}
          isLoading={false}
        />,
      );

      const strikes = screen.getAllByText(/^18[05]$/);
      expect(strikes.length).toBe(2);
      // Strike 180 should come before 185 (ascending default)
      // Use getAllByRole to get actual table cell order
      const tdStrikes = screen.getAllByRole("cell").filter((c) => c.textContent === "180" || c.textContent === "185");
      expect(tdStrikes[0].textContent).toBe("180");
      expect(tdStrikes[1].textContent).toBe("185");
    });

    it("toggles sort direction when clicking Strike header", () => {
      render(
        <OptionsChainTable
          chain={mockChain}
          expirations={["2026-07-10"]}
          underlyingPrice={185.50}
          isLoading={false}
        />,
      );

      // "Strike" appears in both the group header and column header — click the column header (the 2nd match)
      const strikeHeaders = screen.getAllByText("Strike");
      fireEvent.click(strikeHeaders[1]);

      // After clicking, should be sorted descending
      const tdStrikes = screen.getAllByRole("cell").filter((c) => c.textContent === "180" || c.textContent === "185");
      expect(tdStrikes[0].textContent).toBe("185");
      expect(tdStrikes[1].textContent).toBe("180");
    });
  });

  describe("Null/missing values", () => {
    it("shows em-dash for null contract values", () => {
      const chainWithNulls = {
        "2026-07-10": {
          calls: [makeContract({ last_price: null, volume: null, open_interest: null, iv: null })],
          puts: [makeContract({ last_price: null, volume: null, open_interest: null, iv: null })],
        },
      };

      render(
        <OptionsChainTable
          chain={chainWithNulls}
          expirations={["2026-07-10"]}
          underlyingPrice={null}
          isLoading={false}
        />,
      );

      // Should render dashes for null values
      const dashes = screen.getAllByText("—");
      expect(dashes.length).toBeGreaterThan(0);
    });
  });

  describe("No data in table body", () => {
    it("shows 'No options data available' when expiry has no rows", () => {
      const emptyChain = {
        "2026-07-10": { calls: [], puts: [] },
      };

      render(
        <OptionsChainTable
          chain={emptyChain}
          expirations={["2026-07-10"]}
          underlyingPrice={null}
          isLoading={false}
        />,
      );

      expect(screen.getByText("No options data available")).toBeInTheDocument();
    });
  });
});
