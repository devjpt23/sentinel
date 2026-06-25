# Known Gaps Cleanup

**Date:** 2026-06-25
**Branch:** `migrate-to-vercel`

## Overview

Address the remaining known gaps from the Streamlit → Next.js migration: PDF export, supply chain choropleth map, and DCF sensitivity heatmap.

---

## Supply Chain Choropleth Map

### Current State

Supply chain page uses a placeholder or missing visualization where Plotly was used on the main branch.

### Solution

Replace with `react-simple-maps` (lightweight, ~15KB) or pure D3 via `d3-geo` + TopoJSON:

- World map with countries colored by supply chain risk score
- Color scale: green (low risk) → yellow → red (high risk)
- Hover tooltip: country name + risk score + exposure level
- Zoom + pan for interactive exploration (optional, nice-to-have)
- Reuses existing `GET /api/data/<ticker>/supply-chain` endpoint data

### Files

| File | Action |
|---|---|
| `web/src/components/supply-chain/SupplyChainMap.tsx` | **NEW** — replace Plotly choropleth |
| `web/src/app/(dashboard)/company/[ticker]/supply-chain/page.tsx` | Modify — render new component |

---

## DCF Sensitivity Heatmap

### Current State

Currently a plain CSS grid with static color coding. Works but lacks visual polish.

### Upgrade

Enhance the existing heatmap grid with proper Recharts integration or an improved CSS grid:

- Color-coded cells: green (positive upside) → white (neutral) → red (negative upside)
- Cell values displayed: % upside for each (WACC × Growth) combination
- Highlight current assumptions row/column
- Hover tooltip: exact WACC, growth rate, and fair value
- Responsive — scroll horizontally on mobile

### Files

| File | Action |
|---|---|
| `web/src/components/company/DcfHeatmap.tsx` | Modify — upgrade CSS grid with Recharts or enhanced styling |

---

## Files Summary

| File | Action |
|---|---|
| `web/src/components/supply-chain/SupplyChainMap.tsx` | **NEW** |
| `web/src/app/(dashboard)/company/[ticker]/supply-chain/page.tsx` | Modify |
| `web/src/components/company/DcfHeatmap.tsx` | Modify |
