"""
Intrinsic Worth Engine.
Measures what the company is ACTUALLY worth — independent of market sentiment.

Unlike relative valuation (P/E vs peers), intrinsic valuation asks:
"If I bought this entire company today, would the cash it generates
over time justify the price?"

Uses multiple methods:
  - Graham Number (conservative fair value based on earnings + book)
  - FCF Yield (cash return on your investment)
  - P/B absolute (what you pay vs accounting value)
  - Simple Earnings Power Value (EPV)
"""

from typing import Dict, Any, Optional, Tuple


def compute_intrinsic_worth(data: Dict[str, Any]) -> Tuple[int, str, str, str, Dict[str, Any]]:
    """Compute intrinsic worth score (0-100, higher = better value).

    Returns:
        (score_0_100, verdict_label, verdict_explanation, detail_notes, breakdown_dict)
    """
    valuation = data.get("valuation", {})
    market = data.get("market", {})
    health = data.get("health", {})
    per_share = data.get("per_share", {})

    breakdown = {}
    cheap_points = 0
    expensive_points = 0
    total_weight = 0
    notes = []

    price = market.get("price") or 0

    # ─── 1. Graham Number — 30 pts (heaviest weight) ───
    gn = valuation.get("graham_number")
    if gn and price and price > 0 and gn > 0:
        total_weight += 30
        ratio = price / gn
        breakdown["graham_ratio"] = round(ratio, 1)
        breakdown["graham_number"] = round(gn, 2)

        if ratio < 0.7:
            cheap_points += 30
            notes.append(f"Trades at {ratio:.1f}x Graham Number (${gn:.0f}) — well below conservative fair value")
        elif ratio < 1.0:
            cheap_points += 22
            notes.append(f"Trades at {ratio:.1f}x Graham Number (${gn:.0f}) — slightly below conservative fair value")
        elif ratio < 1.5:
            cheap_points += 10
            expensive_points += 8
            notes.append(f"Trades at {ratio:.1f}x Graham Number (${gn:.0f}) — modestly above conservative fair value")
        elif ratio < 3.0:
            expensive_points += 18
            notes.append(f"Trades at {ratio:.1f}x Graham Number (${gn:.0f}) — significantly above conservative fair value")
        elif ratio < 5.0:
            expensive_points += 26
            notes.append(f"Trades at {ratio:.1f}x Graham Number (${gn:.0f}) — far above what conservative valuation supports")
        else:
            expensive_points += 30
            notes.append(f"Trades at {ratio:.1f}x Graham Number (${gn:.0f}) — extremely above conservative fair value")
    else:
        breakdown["graham_ratio"] = None
        breakdown["graham_number"] = None
        notes.append("Graham Number unavailable (requires positive earnings and book value)")

    # ─── 2. FCF Yield — 25 pts ───
    fcf = health.get("fcf")
    market_cap = market.get("market_cap")
    if fcf and market_cap and market_cap > 0:
        total_weight += 25
        fcf_yield = fcf / market_cap
        breakdown["fcf_yield"] = round(fcf_yield * 100, 2)

        if fcf_yield > 0.08:
            cheap_points += 25
            notes.append(f"FCF yield of {fcf_yield:.1%} is excellent — the business generates strong cash relative to its price")
        elif fcf_yield > 0.05:
            cheap_points += 18
            notes.append(f"FCF yield of {fcf_yield:.1%} is good — you're getting solid cash returns for your investment")
        elif fcf_yield > 0.03:
            cheap_points += 10
            notes.append(f"FCF yield of {fcf_yield:.1%} is moderate")
        elif fcf_yield > 0.01:
            expensive_points += 8
            notes.append(f"FCF yield of {fcf_yield:.1%} is low — the company generates little cash relative to its price tag")
        elif fcf_yield > 0:
            expensive_points += 16
            notes.append(f"FCF yield of {fcf_yield:.1%} is very low — you're paying a lot for very little cash generation")
        else:
            expensive_points += 20
            notes.append(f"Negative FCF yield — the company is burning cash")
    else:
        breakdown["fcf_yield"] = None
        notes.append("FCF yield unavailable")

    # ─── 3. P/B Absolute — 20 pts ───
    pb = valuation.get("pb_ratio")
    if pb and pb > 0:
        total_weight += 20
        breakdown["pb_ratio"] = round(pb, 1)

        if pb < 0.8:
            cheap_points += 20
            notes.append(f"P/B of {pb:.1f} — stock trades below its accounting book value (potential bargain or value trap)")
        elif pb < 1.5:
            cheap_points += 12
            notes.append(f"P/B of {pb:.1f} — close to book value, reasonable price for the assets")
        elif pb < 3.0:
            cheap_points += 5
            notes.append(f"P/B of {pb:.1f} — moderate premium over book value")
        elif pb < 5.0:
            expensive_points += 5
            notes.append(f"P/B of {pb:.1f} — significant premium over book value. The market values intangibles (brand, tech, market position) far above tangible assets")
        elif pb < 10:
            expensive_points += 12
            notes.append(f"P/B of {pb:.1f} — very high. You're paying many times what the company's assets are worth on paper")
        elif pb < 20:
            expensive_points += 18
            notes.append(f"P/B of {pb:.1f} — extremely high. The business model must generate extraordinary returns to justify this")
        else:
            expensive_points += 20
            notes.append(f"P/B of {pb:.1f} — the stock price has almost no relationship to the company's accounting value")
    else:
        breakdown["pb_ratio"] = None

    # ─── 4. Earnings Power — 15 pts (simple EPV = EPS / required return) ───
    eps = per_share.get("eps_ttm")
    if eps and eps > 0 and price and price > 0:
        total_weight += 15
        # Simple earnings power: what P/E would a no-growth company deserve?
        # Using 8% required return → fair P/E = 12.5
        fair_pe = 12.5
        fair_value = eps * fair_pe
        ratio = price / fair_value
        breakdown["earnings_power_value"] = round(fair_value, 2)
        breakdown["epv_ratio"] = round(ratio, 1)

        if ratio < 0.7:
            cheap_points += 15
        elif ratio < 1.0:
            cheap_points += 10
            notes.append(f"Even with zero growth, the company's earnings power supports a value of ${fair_value:.0f}/share — the stock is within a fair range")
        elif ratio < 1.5:
            expensive_points += 5
            notes.append(f"No-growth earnings power value is ${fair_value:.0f}/share — the stock trades above what current earnings alone justify, so growth is required")
        elif ratio < 3.0:
            expensive_points += 10
            notes.append(f"No-growth earnings power value is only ${fair_value:.0f}/share — the stock needs significant future growth to justify its current price of ${price:.0f}")
        else:
            expensive_points += 15
            notes.append(f"No-growth earnings power value is just ${fair_value:.0f}/share — the stock at ${price:.0f} requires extraordinary future growth to justify the price")
    else:
        breakdown["earnings_power_value"] = None
        breakdown["epv_ratio"] = None
        if eps is not None and eps <= 0:
            notes.append("Company is not currently profitable — earnings power cannot be calculated")

    # ─── 5. Dividend Support — 10 pts ───
    div_yield = per_share.get("dividend_yield")
    payout = per_share.get("payout_ratio")
    if div_yield is not None and div_yield > 0:
        total_weight += 10
        breakdown["dividend_yield"] = round(div_yield * 100, 2)

        if div_yield > 0.04:
            cheap_points += 10
            notes.append(f"Dividend yield of {div_yield:.1%} provides meaningful income support to the valuation")
        elif div_yield > 0.02:
            cheap_points += 6
            notes.append(f"Dividend yield of {div_yield:.1%} provides modest income support")
        elif div_yield > 0.01:
            cheap_points += 3
        else:
            cheap_points += 1
            notes.append(f"Dividend yield of {div_yield:.1%} provides minimal valuation support")

        if payout and payout > 0.9:
            expensive_points += 5
            notes.append(f"Warning: payout ratio of {payout:.0%} — the dividend may not be sustainable")
    else:
        breakdown["dividend_yield"] = None
        # No penalty for no dividend — growth companies shouldn't pay one

    # ─── Aggregate ───
    if total_weight == 0:
        return 50, "Uncertain", "Not enough data to assess intrinsic worth.", "", breakdown

    net = cheap_points - expensive_points
    normalized = 50 + (net / total_weight) * 50
    normalized = max(0, min(100, round(normalized)))

    if normalized >= 72:
        verdict = "Undervalued"
        explanation = "The stock appears genuinely cheap based on what the business is worth. Conservative measures suggest you're paying less than the company's true value."
    elif normalized >= 56:
        verdict = "Slightly Undervalued"
        explanation = "The stock trades a bit below what conservative measures suggest it's worth. There may be a margin of safety."
    elif normalized >= 44:
        verdict = "Fair"
        explanation = "The stock trades near what conservative measures suggest it's worth. The price roughly matches the business value."
    elif normalized >= 28:
        verdict = "Overvalued"
        explanation = "The stock trades above what conservative measures suggest it's worth. You're paying a premium — the market expects growth that may or may not happen."
    else:
        verdict = "Expensive"
        explanation = "The stock trades far above what the underlying business can justify by conservative measures. The market is pricing in very optimistic assumptions."

    # Build explanation from notes
    full_explanation = " ".join(notes)

    return normalized, verdict, explanation, full_explanation, breakdown
