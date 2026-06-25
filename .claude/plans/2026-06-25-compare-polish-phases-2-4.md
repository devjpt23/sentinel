# Compare Polish — Stock Comparison Phases 2-4

**Date:** 2026-06-25
**Branch:** `migrate-to-vercel`

## Overview

Complete the stock comparison feature with visualizations (radar, scatter), UX enhancements (auto peers, company page button, watchlist quick-compare), and polish (CSV export, returns heatmap, comparison history, column customization).

---

## Phase 2 — Visualizations

### CompareRadar (`web/src/components/charts/CompareRadar.tsx`)

Recharts `RadarChart` with 6 normalized axes (0-100):
- **Value** — composite of P/E, P/B, P/S normalized vs market median
- **Health** — health score (already 0-100)
- **Growth** — composite of revenue growth + earnings growth + price growth
- **Profitability** — composite of margins + ROE + ROIC
- **Safety** — inverted risk score (100 - risk)
- **Momentum** — 6m + 12m price growth normalized

Max 5 tickers per radar (visual clutter limit). Each ticker gets a distinct colored polygon with opacity. Legend below. No new backend data needed — all inputs derive from existing `/api/compare` response fields.

Integration: add a view selector tab bar in the compare page (Chart | Table | Radar | Scatter), default to Chart.

### CompareScatter (`web/src/components/charts/CompareScatter.tsx`)

Extend existing `PeerScatter` component pattern:
- X-axis dropdown: P/E, Market Cap, Debt/Equity, P/B, Dividend Yield
- Y-axis dropdown: Health Score, Growth %, ROE, Risk Score, F-Score
- Each dot labeled with ticker, color-coded by sector
- Tooltip with full metric values
- Responsive, maintains aspect ratio on resize

### Price Overlay Enhancements (`ComparePriceOverlay.tsx`)

- **Rebase toggle**: button to switch between raw price and % rebased (all series normalized to 100 at chart start date). Helps compare relative performance regardless of absolute price differences.
- **Benchmark overlay**: toggle to overlay S&P 500 performance line (fetch from existing market data or hardcoded ETF proxy like SPY)
- **Extended periods**: add 2Y and 5Y to period selector (currently 1M/3M/6M/1Y)

---

## Phase 3 — UX

### Auto Peer Population

When user enters the first ticker in `CompareHeader`:
1. Automatically fetch `GET /api/data/<ticker>/peers` on ticker add
2. Show "Suggested peers from [industry]" drawer below the input
3. Each peer has an "Add" button; header has "Add All" button
4. Store `suggestedPeers: string[]` in `compare-store` Zustand
5. Dismissable drawer — close to hide suggestions

### Company Page "Compare" Button

Add to `web/src/app/(dashboard)/company/[ticker]/page.tsx` header area:
- "Compare to Peers" — fetches peers list, navigates to `/compare?tickers=MU,NVDA,INTC,AMD`
- "Compare with..." — opens a small ticker input dialog, navigates to `/compare?tickers=MU,<user input>`

### Watchlist Quick Compare

- Add checkbox column to `WatchlistTable` (stored in watchlist-store as `selectedForCompare: Set<string>`)
- "Compare Selected (N)" button appears in toolbar when >= 2 selected
- Click navigates to `/compare?tickers=AAPL,MSFT,...`
- Clear selection after navigation

---

## Phase 4 — Polish

### CSV Export

Button in `CompareTable` header: "Export CSV".
- Convert currently-visible metrics + tickers to CSV rows
- Use `columns-to-csv` or simple manual CSV generation (no new dependency needed)
- Triggers browser download via `Blob` + `URL.createObjectURL`

### Returns Heatmap (`web/src/components/charts/ReturnsHeatmap.tsx`)

Finviz-style monthly returns heatmap:
- Rows = tickers, Columns = last 12 months
- Cell color: green for positive return, red for negative, opacity scaled by magnitude
- Tooltip on hover: exact monthly return %
- Pure CSS grid with colored cells — no chart library needed
- Data source: derive monthly returns from `price_history` in compare response

### Comparison History

- On each successful comparison, save `{ tickers, timestamp }` to localStorage (max 5 entries)
- "Recent comparisons" dropdown in `CompareHeader`
- Click to restore a previous ticker set

### Column Customization

- Gear icon in `CompareTable` header toggles a dropdown
- Checkboxes to show/hide metric rows (Price, Mkt Cap, P/E, Health, etc.)
- Visibility preference persisted in `compare-store`

---

## Files Summary

| File | Action | Phase |
|---|---|---|
| `web/src/components/charts/CompareRadar.tsx` | **NEW** | 2 |
| `web/src/components/charts/CompareScatter.tsx` | **NEW** | 2 |
| `web/src/components/compare/ComparePriceOverlay.tsx` | Modify | 2 |
| `web/src/app/(dashboard)/compare/page.tsx` | Modify (view tabs) | 2 |
| `web/src/components/compare/CompareHeader.tsx` | Modify (auto peers) | 3 |
| `web/src/stores/compare-store.ts` | Modify (suggestedPeers) | 3 |
| `web/src/app/(dashboard)/company/[ticker]/page.tsx` | Modify (compare buttons) | 3 |
| `web/src/components/watchlist/WatchlistTable.tsx` | Modify (checkboxes) | 3 |
| `web/src/stores/watchlist-store.ts` | Modify (selectedForCompare) | 3 |
| `web/src/components/compare/CompareTable.tsx` | Modify (CSV export, column customization) | 4 |
| `web/src/components/charts/ReturnsHeatmap.tsx` | **NEW** | 4 |

No backend changes needed beyond what already exists.
