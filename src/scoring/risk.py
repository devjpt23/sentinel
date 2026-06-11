"""
Risk assessment engine.
Evaluates multiple dimensions of risk: financial, market, and business.
"""

from typing import Dict, Any, Optional, Tuple, List


def compute_risk_assessment(data: Dict[str, Any], z_score: Optional[float], z_zone: str) -> Tuple[int, str, str, List[Tuple[str, str, str]]]:
    """Compute overall risk score (0-100, higher = lower risk).

    Returns:
        (score_0_100, risk_label, summary, list_of_risk_factors)
    """
    health = data.get("health", {})
    market = data.get("market", {})
    profitability = data.get("profitability", {})
    valuation = data.get("valuation", {})

    risk_factors = []
    deductions = 0
    max_deductions = 50  # start from 100, deduct for each risk factor

    # 1. Bankruptcy risk (Z-Score) — 15 points max deduction
    if z_score is None:
        risk_factors.append((
            "warning",
            "Unknown bankruptcy risk",
            "We couldn't calculate the Z-Score due to insufficient data. This is common for small or recently listed companies."
        ))
        deductions += 7
    elif z_zone == "Distress":
        risk_factors.append((
            "danger",
            "Balance sheet weakness",
            f"Z-Score of {z_score} indicates elevated bankruptcy risk. The company's balance sheet shows signs of financial strain."
        ))
        deductions += 15
    elif z_zone == "Grey":
        risk_factors.append((
            "warning",
            "Moderate balance sheet risk",
            f"Z-Score of {z_score} falls in the grey zone — not critical, but the balance sheet is not as strong as it could be."
        ))
        deductions += 5
    else:
        risk_factors.append((
            "safe",
            "Strong balance sheet",
            f"Z-Score of {z_score} indicates very low bankruptcy risk."
        ))

    # 2. Debt level — 10 points max
    de = health.get("debt_to_equity")
    if de and de > 200:
        risk_factors.append((
            "danger",
            "Heavy debt load",
            f"Debt-to-equity of {de:.0f}% is very high — the company is heavily leveraged. A downturn could be dangerous."
        ))
        deductions += 10
    elif de and de > 100:
        risk_factors.append((
            "warning",
            "Elevated debt",
            f"Debt-to-equity of {de:.0f}% is above the 100% threshold. The company carries significant debt."
        ))
        deductions += 5
    elif de is not None:
        risk_factors.append((
            "safe",
            "Manageable debt",
            f"Debt-to-equity of {de:.0f}% is at a reasonable level."
        ))

    # 3. Interest coverage — 8 points max
    ic = health.get("interest_coverage")
    if ic is not None and ic < 2:
        risk_factors.append((
            "danger",
            "Struggles to cover interest",
            f"Interest coverage of {ic:.1f}x — the company barely earns enough to pay its interest obligations."
        ))
        deductions += 8
    elif ic is not None and ic < 5:
        risk_factors.append((
            "warning",
            "Tight interest coverage",
            f"Interest coverage of {ic:.1f}x is below the ideal 5x threshold. Worth watching."
        ))
        deductions += 3
    elif ic is not None:
        risk_factors.append((
            "safe",
            "Comfortable interest coverage",
            f"Interest coverage of {ic:.1f}x — the company comfortably covers its interest payments."
        ))

    # 4. Beta / Volatility — 5 points max
    beta = market.get("beta")
    if beta and beta > 2.0:
        risk_factors.append((
            "warning",
            "Very high volatility",
            f"Beta of {beta:.1f} means this stock swings twice as much as the market. Expect a bumpy ride."
        ))
        deductions += 5
    elif beta and beta > 1.5:
        risk_factors.append((
            "warning",
            "High volatility",
            f"Beta of {beta:.1f} means this stock moves significantly more than the market."
        ))
        deductions += 2
    elif beta is not None:
        risk_factors.append((
            "safe",
            "Moderate volatility",
            f"Beta of {beta:.1f} — volatility is in a normal range."
        ))

    # 5. Profitability check — 7 points max
    ni_margin = profitability.get("net_margin")
    if ni_margin is not None and ni_margin < 0:
        risk_factors.append((
            "danger",
            "Losing money",
            f"Net margin of {ni_margin:.1%} — the company is not profitable right now."
        ))
        deductions += 7
    elif ni_margin is not None and ni_margin < 0.03:
        risk_factors.append((
            "warning",
            "Thin profitability",
            f"Net margin of {ni_margin:.1%} is very thin — there's little room for error."
        ))
        deductions += 3

    # 6. Cash vs debt — 5 points max
    cash = health.get("total_cash")
    total_debt = health.get("total_debt")
    if cash is not None and total_debt is not None and total_debt > 0:
        if cash > total_debt:
            risk_factors.append((
                "safe",
                "More cash than debt",
                f"The company holds more cash (${_fmt(cash)}) than total debt (${_fmt(total_debt)})."
            ))
        else:
            risk_factors.append((
                "warning",
                "Debt exceeds cash",
                f"Total debt (${_fmt(total_debt)}) exceeds cash reserves (${_fmt(cash)})."
            ))
            deductions += 5

    # Calculate final score
    score = max(0, 100 - deductions)

    # Determine risk label
    if score >= 70:
        label = "Low"
        summary = "This company appears financially stable with manageable risks."
    elif score >= 40:
        label = "Medium"
        summary = "There are some risk factors to be aware of, but nothing critical."
    else:
        label = "High"
        summary = "There are significant risk factors that deserve careful attention before investing."

    return score, label, summary, risk_factors


def compute_red_flags(data: Dict[str, Any], risk_factors: List) -> List[Tuple[str, str, str]]:
    """Identify specific red flags that deserve attention.

    Returns list of (severity: danger|warning, title, explanation)
    """
    flags = []
    health = data.get("health", {})
    profitability = data.get("profitability", {})
    valuation = data.get("valuation", {})
    growth = data.get("growth", {})

    # Cash flow < Net Income (aggressive accounting)
    ocf = health.get("operating_cash_flow")
    ni_margin = profitability.get("net_margin")
    if ocf is not None and ocf < 0:
        flags.append((
            "danger",
            "Burning cash from operations",
            "The company is spending more cash than it brings in from its core business. This is unsustainable long-term without external funding."
        ))

    # High P/E with slowing growth
    pe = valuation.get("pe_ttm")
    rev_growth = growth.get("revenue_growth_yoy")
    if pe and rev_growth is not None and pe > 30 and rev_growth < 0.05:
        flags.append((
            "warning",
            "High price but slow growth",
            f"P/E of {pe:.0f} is high but revenue growth is only {rev_growth:.1%}. The high valuation may not be justified."
        ))

    # Negative earnings
    eps = data.get("per_share", {}).get("eps_ttm")
    if eps is not None and eps < 0:
        flags.append((
            "danger",
            "Negative earnings",
            "The company lost money over the last 12 months. This may be temporary (turnaround) or structural (decline)."
        ))

    # Debt exceeding market cap (extreme leverage)
    de = health.get("debt_to_equity")
    if de and de > 300:
        flags.append((
            "danger",
            "Extreme leverage",
            f"Debt-to-equity of {de:.0f}% is exceptionally high. The company could be in serious trouble if earnings decline."
        ))

    # Cash vs. total debt — debt exceeding cash is a key distress signal
    cash = health.get("total_cash")
    total_debt = health.get("total_debt")
    if cash is not None and total_debt is not None and total_debt > 0 and cash < total_debt:
        ratio = total_debt / cash if cash > 0 else float("inf")
        flags.append((
            "warning" if ratio < 3 else "danger",
            "Debt exceeds cash reserves",
            f"Total debt (${_fmt(total_debt)}) is {ratio:.1f}x the company's cash (${_fmt(cash)}). "
            + ("The company can cover its debt with available cash." if ratio < 2
               else "The company may struggle to service its debt in a downturn.")
        ))

    # Dividend payout ratio > 100%
    payout = data.get("per_share", {}).get("payout_ratio")
    if payout and payout > 1.0:
        flags.append((
            "warning",
            "Unsustainable dividend",
            f"The company pays out {payout:.0%} of earnings as dividends — more than it earns. The dividend may be cut."
        ))

    # Add risk factors marked as danger/warning
    for severity, title, explanation in risk_factors:
        if severity in ("danger", "warning"):
            flags.append((severity, title, explanation))

    return flags


def _fmt(val: Optional[float]) -> str:
    if val is None:
        return "N/A"
    if abs(val) >= 1e9:
        return f"${val/1e9:.1f}B"
    if abs(val) >= 1e6:
        return f"${val/1e6:.1f}M"
    return f"${val:,.0f}"
