"""
Price verdict engine.
Determines if a stock is undervalued, fairly valued, or overvalued.

Uses multiple independent signals — no single metric dominates.
Peer comparisons use MEDIAN (not mean) to resist outlier distortion.
"""

from typing import Dict, Any, Optional, Tuple


def compute_price_verdict(data: Dict[str, Any], peer_averages: Dict[str, Optional[float]]) -> Tuple[int, str, str, str]:
    """Compute price verdict score (0-100, higher = better value).

    Returns:
        (score_0_100, verdict_label, short_verdict, detailed_explanation)
    """
    valuation = data.get("valuation", {})
    growth = data.get("growth", {})
    market = data.get("market", {})

    cheap_points = 0
    expensive_points = 0
    total_weight = 0
    explanations = []

    # ─── 1. P/E TTM vs peers (MEDIAN) — 20 pts ───
    pe = valuation.get("pe_ttm")
    pe_peer = peer_averages.get("pe_ttm")
    if pe and pe_peer and pe_peer > 0 and pe > 0:
        total_weight += 20
        ratio = pe / pe_peer
        if ratio < 0.75:
            cheap_points += 20
            explanations.append(f"P/E of {pe:.0f} is well below the sector median of {pe_peer:.0f} — you're paying significantly less than peers for each dollar of earnings")
        elif ratio < 0.90:
            cheap_points += 14
            explanations.append(f"P/E of {pe:.0f} is below the sector median of {pe_peer:.0f} — a modest discount to peers")
        elif ratio < 1.15:
            cheap_points += 10
            expensive_points += 0
            explanations.append(f"P/E of {pe:.0f} is close to the sector median of {pe_peer:.0f} — fairly priced relative to peers")
        elif ratio < 1.50:
            expensive_points += 8
            explanations.append(f"P/E of {pe:.0f} is above the sector median of {pe_peer:.0f} — you're paying a premium")
        else:
            expensive_points += 15
            explanations.append(f"P/E of {pe:.0f} is significantly above the sector median of {pe_peer:.0f} — the stock looks expensive vs peers")
    elif pe and pe > 0:
        # No peer data — use absolute thresholds
        total_weight += 15
        if pe < 12:
            cheap_points += 15
            explanations.append(f"P/E of {pe:.0f} is low in absolute terms")
        elif pe < 20:
            cheap_points += 10
            explanations.append(f"P/E of {pe:.0f} is moderate")
        elif pe < 30:
            expensive_points += 5
            explanations.append(f"P/E of {pe:.0f} is above average")
        else:
            expensive_points += 12
            explanations.append(f"P/E of {pe:.0f} is high — the market expects strong future growth to justify this")

    # ─── 2. Forward P/E — 15 pts ───
    pe_fwd = valuation.get("pe_forward")
    pe_fwd_peer = peer_averages.get("pe_forward")
    if pe_fwd and pe_fwd > 0:
        total_weight += 15
        if pe_fwd_peer and pe_fwd_peer > 0:
            ratio = pe_fwd / pe_fwd_peer
            if ratio < 0.75:
                cheap_points += 15
                explanations.append(f"Forward P/E of {pe_fwd:.0f} is well below the peer median of {pe_fwd_peer:.0f} — the stock looks cheap on expected earnings")
            elif ratio < 0.90:
                cheap_points += 10
                explanations.append(f"Forward P/E of {pe_fwd:.0f} is below peers — modestly attractive on a forward basis")
            elif ratio < 1.15:
                cheap_points += 7
                explanations.append(f"Forward P/E of {pe_fwd:.0f} is in line with peers")
            elif ratio < 1.50:
                expensive_points += 5
                explanations.append(f"Forward P/E of {pe_fwd:.0f} is above peers on expected earnings")
            else:
                expensive_points += 12
                explanations.append(f"Forward P/E of {pe_fwd:.0f} is significantly above peers — even future earnings look expensive")
        else:
            # Absolute forward P/E check
            if pe_fwd < 12:
                cheap_points += 12
                explanations.append(f"Forward P/E of {pe_fwd:.0f} suggests strong earnings growth ahead at a reasonable price")
            elif pe_fwd < 18:
                cheap_points += 7
                explanations.append(f"Forward P/E of {pe_fwd:.0f} is moderate")
            elif pe_fwd < 25:
                expensive_points += 3
            else:
                expensive_points += 8
                explanations.append(f"Forward P/E of {pe_fwd:.0f} — even projected earnings don't make this look cheap")

    # ─── 3. PEG Ratio — 15 pts ───
    peg = valuation.get("peg_ratio")
    if peg is not None and peg > 0:
        total_weight += 15
        if peg < 0.5:
            # Very low PEG — could be genuinely cheap OR could be a cyclical peak
            # Check if growth rate is unsustainably high
            rev_g = growth.get("revenue_growth_yoy")
            if rev_g and rev_g > 1.0:  # >100% growth — likely unsustainable
                cheap_points += 5
                explanations.append(f"PEG of {peg:.1f} is very low but revenue growth of {rev_g*100:.0f}% may not be sustainable — this could be a cyclical peak")
            else:
                cheap_points += 12
                explanations.append(f"PEG of {peg:.1f} suggests the stock is undervalued relative to its growth rate")
        elif peg < 0.8:
            cheap_points += 10
            explanations.append(f"PEG of {peg:.1f} suggests good value given its growth rate")
        elif peg < 1.2:
            cheap_points += 6
            explanations.append(f"PEG of {peg:.1f} suggests the stock is fairly valued for its growth")
        elif peg < 2.0:
            expensive_points += 6
            explanations.append(f"PEG of {peg:.1f} suggests the stock may be slightly expensive even with growth")
        else:
            expensive_points += 12
            explanations.append(f"PEG of {peg:.1f} suggests the stock is overvalued relative to its growth")
    elif peg is not None and peg < 0:
        total_weight += 8
        expensive_points += 8
        explanations.append("Negative PEG ratio — earnings are declining, which is a warning sign")

    # ─── 4. Graham Number — 20 pts (HEAVY WEIGHT) ───
    gn = valuation.get("graham_number")
    price = market.get("price")
    if gn and price and price > 0 and gn > 0:
        total_weight += 20
        ratio = price / gn
        if ratio < 0.8:
            cheap_points += 20
            explanations.append(f"The stock trades well below its Graham fair value of ${gn:.0f} — potential bargain by conservative measures")
        elif ratio < 1.0:
            cheap_points += 12
            explanations.append(f"The stock trades slightly below its Graham fair value of ${gn:.0f} — reasonable value")
        elif ratio < 1.5:
            cheap_points += 4
            expensive_points += 4
            explanations.append(f"The stock trades modestly above its Graham fair value of ${gn:.0f}")
        elif ratio < 3.0:
            expensive_points += 12
            explanations.append(f"The stock trades at {ratio:.1f}x its Graham fair value of ${gn:.0f} — significantly above conservative fair value")
        elif ratio < 5.0:
            expensive_points += 18
            explanations.append(f"The stock trades at {ratio:.1f}x its Graham fair value of ${gn:.0f} — far above what conservative valuation suggests")
        else:
            expensive_points += 20
            explanations.append(f"The stock trades at {ratio:.1f}x its Graham fair value of ${gn:.0f} — extremely expensive by Graham's measures. This suggests either the stock is very overvalued or Graham's simple formula doesn't capture this business model")
    elif gn is None:
        explanations.append("Graham Number couldn't be calculated (negative earnings or book value)")

    # ─── 5. P/B absolute check — 10 pts ───
    pb = valuation.get("pb_ratio")
    if pb:
        total_weight += 10
        if pb > 20:
            expensive_points += 10
            explanations.append(f"Price-to-book of {pb:.1f} is extremely high — you're paying over 20x the accounting value of assets")
        elif pb > 10:
            expensive_points += 6
            explanations.append(f"Price-to-book of {pb:.1f} is very high — the market values this company far above its asset base")
        elif pb > 5:
            expensive_points += 2
            explanations.append(f"Price-to-book of {pb:.1f} is elevated")
        elif pb < 1.0:
            cheap_points += 8
            explanations.append(f"Price-to-book of {pb:.1f} is below 1.0 — the stock trades below its accounting value (potential bargain or value trap)")
        elif pb < 1.5:
            cheap_points += 4
            explanations.append(f"Price-to-book of {pb:.1f} is reasonable")

    # ─── 6. EV/EBITDA vs peers — 10 pts ───
    ev_ebitda = valuation.get("ev_ebitda")
    ev_peer = peer_averages.get("ev_ebitda")
    if ev_ebitda and ev_peer and ev_peer > 0 and ev_ebitda > 0:
        total_weight += 10
        ratio = ev_ebitda / ev_peer
        if ratio < 0.75:
            cheap_points += 10
            explanations.append(f"EV/EBITDA of {ev_ebitda:.0f}x is well below the peer median of {ev_peer:.0f}x")
        elif ratio < 0.90:
            cheap_points += 6
        elif ratio < 1.15:
            cheap_points += 5
        elif ratio < 1.50:
            expensive_points += 4
            explanations.append(f"EV/EBITDA of {ev_ebitda:.0f}x is above the peer median of {ev_peer:.0f}x")
        else:
            expensive_points += 8
            explanations.append(f"EV/EBITDA of {ev_ebitda:.0f}x is significantly above peers at {ev_peer:.0f}x")

    # ─── 7. P/S vs peers — 10 pts ───
    ps = valuation.get("ps_ratio")
    ps_peer = peer_averages.get("ps_ratio")
    if ps and ps_peer and ps_peer > 0 and ps > 0:
        total_weight += 10
        ratio = ps / ps_peer
        if ratio < 0.75:
            cheap_points += 10
        elif ratio < 0.90:
            cheap_points += 6
        elif ratio < 1.15:
            cheap_points += 5
        elif ratio < 1.50:
            expensive_points += 4
        else:
            expensive_points += 8
            explanations.append(f"Price-to-sales of {ps:.1f}x is well above peers at {ps_peer:.1f}x")

    # ─── 8. Cyclical Earnings Gap — 10 pts ───
    # When Forward P/E is MUCH lower than TTM P/E, it means analysts expect
    # earnings to surge dramatically. This often happens at cyclical peaks
    # (semiconductors, energy, commodities). If those estimates are wrong,
    # the stock is actually very expensive.
    if pe and pe_fwd and pe > 0 and pe_fwd > 0:
        total_weight += 10
        gap_ratio = pe / pe_fwd
        if gap_ratio > 5.0:
            expensive_points += 10
            explanations.append(f"Forward P/E ({pe_fwd:.0f}) is {gap_ratio:.0f}x lower than TTM P/E ({pe:.0f}) — analysts expect earnings to surge over 5x. This is common in cyclical industries at peak optimism. If estimates are wrong, the stock is actually very expensive on current earnings")
        elif gap_ratio > 3.0:
            expensive_points += 6
            explanations.append(f"Forward P/E ({pe_fwd:.0f}) is {gap_ratio:.0f}x lower than TTM P/E ({pe:.0f}) — a large earnings jump is priced in. This adds risk if the expected recovery doesn't materialize")
        elif gap_ratio > 2.0:
            expensive_points += 3
            explanations.append(f"Forward P/E ({pe_fwd:.0f}) is significantly lower than TTM P/E ({pe:.0f}) — meaningful earnings improvement expected")

    # ─── Aggregate ───
    if total_weight == 0:
        return 50, "Uncertain", "Not enough data to judge price", "We don't have sufficient data to make a price assessment."

    # Net: positive = good value, negative = expensive
    net = cheap_points - expensive_points
    max_possible = total_weight

    # Map to 0-100 scale
    # net = +max_possible -> score 100 (extremely undervalued)
    # net = 0 -> score 50 (fair)
    # net = -max_possible -> score 0 (extremely overvalued)
    normalized = 50 + (net / max_possible) * 50
    normalized = max(0, min(100, round(normalized)))

    # Determine verdict
    if normalized >= 72:
        verdict = "Undervalued"
        short = "Trading below fair value — potential bargain"
    elif normalized >= 56:
        verdict = "Slightly Undervalued"
        short = "Trading a bit below fair value"
    elif normalized >= 44:
        verdict = "Fair"
        short = "Trading close to fair value"
    elif normalized >= 28:
        verdict = "Slightly Overvalued"
        short = "Trading above fair value — consider waiting for a pullback"
    else:
        verdict = "Overvalued"
        short = "Trading well above fair value — may be expensive"

    detail = " ".join(explanations)
    return normalized, verdict, short, detail
