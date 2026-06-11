"""
Discounted Cash Flow (DCF) valuation model.
Estimates intrinsic value by projecting future free cash flows
and discounting them back to today's dollars.
"""

from typing import Dict, Any, Optional, Tuple
import numpy as np


def compute_dcf(
    data: Dict[str, Any],
    revenue_growth_5yr: float = 0.10,
    terminal_growth: float = 0.03,
    discount_rate: float = 0.10,
    margin_improvement: float = 0.0,
) -> Dict[str, Any]:
    """Build a 5-year DCF model with customizable assumptions.

    Args:
        data: Company data dict from fetcher
        revenue_growth_5yr: Annual revenue growth rate for projection period (0.10 = 10%)
        terminal_growth: Perpetual growth rate after projection period (0.03 = 3%)
        discount_rate: WACC / required rate of return (0.10 = 10%)
        margin_improvement: Annual FCF margin improvement (0.01 = margins expand 1%/yr)

    Returns:
        Dict with projected cash flows, fair value, sensitivity, and explanation
    """
    health = data.get("health", {})
    market = data.get("market", {})
    profitability = data.get("profitability", {})
    growth_data = data.get("growth", {})
    statements = data.get("statements", {})

    # ─── Starting Values ───
    current_revenue = _get_current_revenue(statements)
    current_fcf = health.get("fcf")
    shares = market.get("shares_outstanding") or _get_shares_from_statements(statements)
    current_price = market.get("price")

    if not current_revenue or not current_fcf or not shares or shares <= 0:
        return {
            "error": "Insufficient data for DCF — need revenue, free cash flow, and shares outstanding.",
            "fair_value": None,
            "upside_pct": None,
        }

    # Current FCF margin
    current_fcf_margin = current_fcf / current_revenue if current_revenue > 0 else 0.05

    # ─── Project 5 Years of FCF ───
    projected_fcf = []
    projected_revenue = []
    revenue = current_revenue
    fcf_margin = current_fcf_margin + margin_improvement  # starting margin with improvement

    for year in range(1, 6):
        revenue = revenue * (1 + revenue_growth_5yr)
        # Margin improves each year but is capped at 40% (very few companies exceed this)
        fcf_margin = min(fcf_margin + margin_improvement, 0.40)
        fcf = revenue * fcf_margin

        projected_revenue.append(revenue)
        projected_fcf.append(fcf)

    # ─── Terminal Value ───
    # Gordon Growth Model: TV = FCF_year5 * (1 + g) / (r - g)
    terminal_fcf = projected_fcf[-1] * (1 + terminal_growth)
    if discount_rate > terminal_growth:
        terminal_value = terminal_fcf / (discount_rate - terminal_growth)
    else:
        terminal_value = terminal_fcf / 0.02  # floor if assumptions are invalid

    # ─── Discount Everything to Present ───
    pv_fcf = []
    for year, fcf in enumerate(projected_fcf, 1):
        pv = fcf / ((1 + discount_rate) ** year)
        pv_fcf.append(pv)

    pv_terminal = terminal_value / ((1 + discount_rate) ** 5)
    enterprise_value = sum(pv_fcf) + pv_terminal

    # ─── Per-Share Fair Value ───
    fair_value_per_share = enterprise_value / shares

    # ─── Net Cash Adjustment ───
    cash = health.get("total_cash") or 0
    total_debt = health.get("total_debt") or 0
    net_cash = cash - total_debt
    net_cash_per_share = net_cash / shares if shares > 0 else 0
    fair_value_with_cash = fair_value_per_share + net_cash_per_share

    # ─── Upside / Downside ───
    if current_price and current_price > 0:
        upside_pct = ((fair_value_with_cash / current_price) - 1) * 100
    else:
        upside_pct = None

    # ─── Sensitivity Matrix ───
    sensitivity = _build_sensitivity(
        current_revenue, current_fcf_margin, margin_improvement,
        shares, revenue_growth_5yr, terminal_growth, discount_rate, current_price
    )

    # ─── Verdict ───
    if upside_pct is not None:
        if upside_pct > 20:
            dcf_verdict = "Significantly Undervalued"
        elif upside_pct > 5:
            dcf_verdict = "Undervalued"
        elif upside_pct > -5:
            dcf_verdict = "Fair Value"
        elif upside_pct > -20:
            dcf_verdict = "Overvalued"
        else:
            dcf_verdict = "Significantly Overvalued"
    else:
        dcf_verdict = "Unknown"

    return {
        "error": None,
        "current_revenue": current_revenue,
        "current_fcf": current_fcf,
        "current_fcf_margin": current_fcf_margin,
        "shares_outstanding": shares,
        "projected_revenue": projected_revenue,
        "projected_fcf": projected_fcf,
        "pv_fcf": pv_fcf,
        "terminal_value": terminal_value,
        "pv_terminal": pv_terminal,
        "enterprise_value": enterprise_value,
        "fair_value_per_share": fair_value_per_share,
        "fair_value_with_cash": fair_value_with_cash,
        "net_cash_per_share": net_cash_per_share,
        "upside_pct": upside_pct,
        "verdict": dcf_verdict,
        "sensitivity": sensitivity,
        "assumptions": {
            "revenue_growth_5yr": revenue_growth_5yr,
            "terminal_growth": terminal_growth,
            "discount_rate": discount_rate,
            "margin_improvement": margin_improvement,
        },
    }


def _build_sensitivity(
    current_revenue: float,
    fcf_margin: float,
    margin_improvement: float,
    shares: float,
    base_rev_growth: float,
    terminal_growth: float,
    base_discount_rate: float,
    current_price: Optional[float],
) -> Dict[str, Any]:
    """Build sensitivity table: upside % at different WACC (x-axis) and
    revenue growth rates (y-axis). These are the two biggest drivers of DCF value."""
    wacc_range = [base_discount_rate - 0.02, base_discount_rate - 0.01,
                  base_discount_rate, base_discount_rate + 0.01, base_discount_rate + 0.02]
    # Vary revenue growth — the most impactful assumption
    growth_range = [max(0.02, base_rev_growth - 0.10),
                    max(0.03, base_rev_growth - 0.05),
                    base_rev_growth,
                    base_rev_growth + 0.05,
                    base_rev_growth + 0.10]

    # Clamp to reasonable bounds
    wacc_range = [max(0.05, min(0.20, w)) for w in wacc_range]
    growth_range = [max(0.01, min(0.60, g)) for g in growth_range]

    matrix = []
    for rev_g in growth_range:
        row = []
        for w in wacc_range:
            if w <= terminal_growth:
                row.append(None)  # invalid: WACC must exceed terminal growth
            else:
                rev = current_revenue
                fcf_m = fcf_margin + margin_improvement
                pv_total = 0
                for yr in range(1, 6):
                    rev = rev * (1 + rev_g)  # use the sensitivity growth rate
                    fcf_m = min(fcf_m + margin_improvement, 0.40)
                    fcf = rev * fcf_m
                    pv_total += fcf / ((1 + w) ** yr)
                term_fcf = rev * fcf_m * (1 + terminal_growth)
                tv = term_fcf / (w - terminal_growth)
                pv_total += tv / ((1 + w) ** 5)
                fv = pv_total / shares if shares > 0 else 0
                if current_price and current_price > 0:
                    row.append(round(((fv / current_price) - 1) * 100, 1))
                else:
                    row.append(round(fv, 2))
        matrix.append(row)

    return {
        "wacc_range": [round(w * 100, 1) for w in wacc_range],
        "growth_range": [round(g * 100, 1) for g in growth_range],
        "matrix": matrix,
        "current_price": current_price,
    }


def _get_current_revenue(statements: Dict) -> Optional[float]:
    """Extract current revenue from income statement."""
    income = statements.get("income")
    if income is None or income.empty:
        return None
    for label in income.index:
        if str(label).strip() in ("Total Revenue", "Revenue"):
            vals = income.loc[label].dropna()
            if not vals.empty:
                return float(vals.iloc[0])
    return None


def _get_shares_from_statements(statements: Dict) -> Optional[float]:
    """Try to get shares outstanding from balance sheet."""
    balance = statements.get("balance")
    if balance is None or balance.empty:
        return None
    for label in balance.index:
        lbl = str(label).lower()
        if "share" in lbl and ("outstanding" in lbl or "common" in lbl):
            vals = balance.loc[label].dropna()
            if not vals.empty:
                return float(abs(vals.iloc[0]))
    return None
