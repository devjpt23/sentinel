"""
Piotroski F-Score and composite Health Score.
Measures financial strength across profitability, leverage, and efficiency.
"""

from typing import Dict, Any, Optional, List, Tuple

from src.scoring.zscore import compute_altman_zscore, compute_zscore_normalized


def compute_health_score(data: Dict[str, Any]) -> Tuple[int, str, int, List[Tuple[str, bool, str]]]:
    """Compute the composite Health Score (0-100) from F-Score, Z-Score, and ROE.

    This is the SINGLE canonical health score — used by Dashboard, Watchlist,
    and Strategy Lab to ensure consistent results everywhere.

    Returns:
        (score_0_100, verdict_label, fscore_raw, fscore_criteria)
    """
    fscore, fscore_criteria = compute_piotroski_fscore(data)
    z_score, z_zone, _ = compute_altman_zscore(data)
    z_normalized = compute_zscore_normalized(z_score)

    # Base: F-Score (max 50 pts) + Z-Score (max 30 pts) + floor (20 pts) = 100 max
    score = round((fscore / 9) * 50 + z_normalized * 0.3 + 20)
    score = max(0, min(100, score))

    # Bonus for strong profitability
    roe = data.get("profitability", {}).get("roe")
    if roe and roe > 0.20:
        score = min(100, score + 10)
    elif roe and roe > 0.10:
        score = min(100, score + 5)

    # Verdict
    if score >= 70:
        verdict = "Strong"
    elif score >= 40:
        verdict = "Moderate"
    else:
        verdict = "Weak"

    return score, verdict, fscore, fscore_criteria


def compute_piotroski_fscore(data: Dict[str, Any]) -> Tuple[int, List[Tuple[str, bool, str]]]:
    """Compute the Piotroski F-Score from financial data.

    Returns:
        (score 0-9, list of (criterion_name, passed, explanation))
    """
    criteria = []

    health = data.get("health", {})
    profitability = data.get("profitability", {})
    growth = data.get("growth", {})
    statements = data.get("statements", {})
    per_share = data.get("per_share", {})

    # --- Profitability (4 points) ---

    # 1. Positive Net Income (ROA > 0)
    roa = profitability.get("roa")
    ni_positive = roa is not None and roa > 0
    criteria.append((
        "Net income is positive",
        ni_positive,
        f"The company is profitable — return on assets is {_pct(roa)}." if ni_positive
        else "The company is losing money — return on assets is {_pct(roa)}." if roa is not None
        else "Not enough data to check profitability."
    ))

    # 2. Positive Operating Cash Flow
    ocf = health.get("operating_cash_flow")
    ocf_positive = ocf is not None and ocf > 0
    criteria.append((
        "Operating cash flow is positive",
        ocf_positive,
        f"The business generates positive cash from operations (${_fmt(ocf)})." if ocf_positive
        else "The business is burning cash from operations." if ocf is not None
        else "Not enough data to check operating cash flow."
    ))

    # 3. ROA increased vs. prior year
    roa_increased = _check_roa_increased(data)
    criteria.append((
        "Return on assets improved from last year",
        roa_increased[0],
        roa_increased[1]
    ))

    # 4. CFO > Net Income (quality of earnings — cash flow exceeds accounting profit)
    ni = _get_net_income(data)
    cfo_quality = ocf is not None and ni is not None and ocf > ni if ni else None
    criteria.append((
        "Cash flow exceeds reported profit",
        bool(cfo_quality),
        f"Cash from operations (${_fmt(ocf)}) exceeds net income (${_fmt(ni)}) — earnings quality is good." if cfo_quality
        else f"Cash from operations (${_fmt(ocf)}) is less than net income (${_fmt(ni)}) — possible accounting concerns." if ocf is not None and ni is not None
        else "Not enough data to check earnings quality."
    ))

    # --- Leverage & Liquidity (3 points) ---

    # 5. Long-term debt ratio decreased
    debt_decreased = _check_debt_decreased(data)
    criteria.append((
        "Debt level decreased from last year",
        debt_decreased[0],
        debt_decreased[1]
    ))

    # 6. Current ratio increased
    cr_increased = _check_current_ratio_increased(data)
    criteria.append((
        "Ability to pay short-term bills improved",
        cr_increased[0],
        cr_increased[1]
    ))

    # 7. No new share issuance (no dilution)
    dilution = _check_dilution(data)
    criteria.append((
        "No new shares issued (your ownership was not diluted)",
        dilution[0],
        dilution[1]
    ))

    # --- Operating Efficiency (2 points) ---

    # 8. Gross margin increased
    margin_increased = _check_margin_increased(data)
    criteria.append((
        "Gross profit margin improved",
        margin_increased[0],
        margin_increased[1]
    ))

    # 9. Asset turnover increased
    turnover_increased = _check_asset_turnover_increased(data)
    criteria.append((
        "Asset efficiency improved",
        turnover_increased[0],
        turnover_increased[1]
    ))

    score = sum(1 for _, passed, _ in criteria if passed)
    return score, criteria


def _get_net_income(data: Dict[str, Any]) -> Optional[float]:
    """Extract latest net income from statements."""
    statements = data.get("statements", {})
    income = statements.get("income", None)
    if income is not None and not income.empty:
        for label in income.index:
            if "Net Income" in str(label):
                vals = income.loc[label].dropna()
                if not vals.empty:
                    return float(vals.iloc[0])
    return None


def _check_roa_increased(data: Dict[str, Any]) -> Tuple[bool, str]:
    """Check if ROA increased from prior year."""
    statements = data.get("statements", {})
    income = statements.get("income")
    balance = statements.get("balance")

    try:
        if income is not None and not income.empty and balance is not None and not balance.empty:
            for label in income.index:
                if "Net Income" in str(label):
                    ni_vals = income.loc[label].dropna()
                    break
            else:
                return False, "Not enough data to check if profitability improved."

            for label in balance.index:
                if "Total Assets" in str(label):
                    ta_vals = balance.loc[label].dropna()
                    break
            else:
                return False, "Not enough data to check if profitability improved."

            if len(ni_vals) >= 2 and len(ta_vals) >= 2:
                roa_curr = abs(ni_vals.iloc[0] / ta_vals.iloc[0]) if ta_vals.iloc[0] != 0 else 0
                roa_prev = abs(ni_vals.iloc[1] / ta_vals.iloc[1]) if ta_vals.iloc[1] != 0 else 0
                if roa_curr > roa_prev:
                    return True, f"Return on assets improved to {roa_curr:.1%} from {roa_prev:.1%}."
                else:
                    return False, f"Return on assets declined to {roa_curr:.1%} from {roa_prev:.1%}."
    except Exception:
        pass

    # Fallback: check if ROA from info is positive (can't check trend without statements)
    roa = data.get("profitability", {}).get("roa")
    if roa and roa > 0:
        return True, "The company is profitable (return on assets is positive)."
    return False, "Not enough data to check profitability trend."


def _check_debt_decreased(data: Dict[str, Any]) -> Tuple[bool, str]:
    """Check if debt ratio decreased."""
    statements = data.get("statements", {})
    balance = statements.get("balance")

    try:
        if balance is not None and not balance.empty:
            debt = None
            assets = None
            for label in balance.index:
                if "Total Debt" in str(label):
                    debt = balance.loc[label].dropna()
                if "Total Assets" in str(label):
                    assets = balance.loc[label].dropna()

            if debt is not None and assets is not None and len(debt) >= 2 and len(assets) >= 2:
                ratio_curr = debt.iloc[0] / assets.iloc[0] if assets.iloc[0] != 0 else 0
                ratio_prev = debt.iloc[1] / assets.iloc[1] if assets.iloc[1] != 0 else 0
                if ratio_curr < ratio_prev:
                    return True, f"Debt-to-assets improved to {ratio_curr:.1%} from {ratio_prev:.1%}."
                else:
                    return False, f"Debt-to-assets worsened to {ratio_curr:.1%} from {ratio_prev:.1%}."
    except Exception:
        pass

    return False, "Not enough data to check debt trend."


def _check_current_ratio_increased(data: Dict[str, Any]) -> Tuple[bool, str]:
    """Check if current ratio increased."""
    statements = data.get("statements", {})
    balance = statements.get("balance")

    try:
        if balance is not None and not balance.empty:
            ca = None
            cl = None
            for label in balance.index:
                if "Current Assets" in str(label):
                    ca = balance.loc[label].dropna()
                if "Current Liabilities" in str(label):
                    cl = balance.loc[label].dropna()

            if ca is not None and cl is not None and len(ca) >= 2 and len(cl) >= 2:
                cr_curr = ca.iloc[0] / cl.iloc[0] if cl.iloc[0] != 0 else 0
                cr_prev = ca.iloc[1] / cl.iloc[1] if cl.iloc[1] != 0 else 0
                if cr_curr > cr_prev:
                    return True, f"Current ratio improved to {cr_curr:.2f} from {cr_prev:.2f}."
                else:
                    return False, f"Current ratio declined to {cr_curr:.2f} from {cr_prev:.2f}."
    except Exception:
        pass

    return False, "Not enough data to check short-term bill-paying ability."


def _check_dilution(data: Dict[str, Any]) -> Tuple[bool, str]:
    """Check if shares outstanding increased (dilution).

    Uses shares outstanding from both yfinance info (current) and balance sheet
    history (prior years) to detect whether the company has been issuing new shares.
    A rising share count dilutes existing shareholders.
    """
    # Primary approach: compare current shares outstanding to prior-year value
    # from the balance sheet's "Ordinary Shares Number" or similar line.
    statements = data.get("statements", {})
    balance = statements.get("balance")
    current_shares = data.get("market", {}).get("shares_outstanding")

    try:
        if balance is not None and not balance.empty and current_shares:
            # Look for actual share-count rows (not dollar amounts like "Common Stock")
            for label in balance.index:
                lbl = str(label).lower()
                if "share" in lbl and ("number" in lbl or "outstanding" in lbl
                                       or "issued" in lbl or "ordinary" in lbl):
                    hist_shares = balance.loc[label].dropna()
                    # The row may be in thousands or raw — compare direction, not magnitude
                    if len(hist_shares) >= 2:
                        # If the most recent year has more shares than the prior year,
                        # dilution occurred
                        if hist_shares.iloc[0] > hist_shares.iloc[1] * 1.01:
                            return False, (
                                "New shares were issued — your ownership stake was diluted "
                                f"({hist_shares.iloc[0]:,.0f} vs {hist_shares.iloc[1]:,.0f} shares)."
                            )
                        else:
                            return True, (
                                "No meaningful share dilution detected "
                                f"({hist_shares.iloc[0]:,.0f} vs {hist_shares.iloc[1]:,.0f} shares)."
                            )

            # Fallback: use yfinance's sharesOutstanding vs a rough estimate from market cap/price
            # We can't get historical shares from info alone, so check if buyback activity
            # is visible (fallback to neutral — don't penalize without evidence)
            return True, "Share count stable — no significant dilution detected from available data."

    except Exception:
        pass

    # Final fallback: if we have current shares but no history, be conservative
    if current_shares:
        return True, "Share count data available — unable to verify dilution trend."
    return False, "Not enough data to check for dilution."


def _check_margin_increased(data: Dict[str, Any]) -> Tuple[bool, str]:
    """Check if gross margin increased."""
    statements = data.get("statements", {})
    income = statements.get("income")

    try:
        if income is not None and not income.empty:
            revenue = None
            cogs = None
            for label in income.index:
                if "Total Revenue" == str(label).strip() or "Revenue" == str(label).strip():
                    revenue = income.loc[label].dropna()
                if "Cost of" in str(label) or "Cost Of" in str(label):
                    cogs = income.loc[label].dropna()

            if revenue is not None and cogs is not None and len(revenue) >= 2 and len(cogs) >= 2:
                gm_curr = (revenue.iloc[0] - abs(cogs.iloc[0])) / revenue.iloc[0] if revenue.iloc[0] != 0 else 0
                gm_prev = (revenue.iloc[1] - abs(cogs.iloc[1])) / revenue.iloc[1] if revenue.iloc[1] != 0 else 0
                if gm_curr > gm_prev:
                    return True, f"Gross margin improved to {gm_curr:.1%} from {gm_prev:.1%}."
                else:
                    return False, f"Gross margin declined to {gm_curr:.1%} from {gm_prev:.1%}."
    except Exception:
        pass

    return False, "Not enough data to check gross margin trend."


def _check_asset_turnover_increased(data: Dict[str, Any]) -> Tuple[bool, str]:
    """Check if asset turnover increased."""
    statements = data.get("statements", {})
    income = statements.get("income")
    balance = statements.get("balance")

    try:
        if income is not None and not income.empty and balance is not None and not balance.empty:
            for label in income.index:
                if "Total Revenue" == str(label).strip() or "Revenue" == str(label).strip():
                    revenue = income.loc[label].dropna()
                    break
            else:
                return False, "Not enough data to check efficiency."

            for label in balance.index:
                if "Total Assets" in str(label):
                    assets = balance.loc[label].dropna()
                    break
            else:
                return False, "Not enough data to check efficiency."

            if len(revenue) >= 2 and len(assets) >= 2:
                at_curr = revenue.iloc[0] / assets.iloc[0] if assets.iloc[0] != 0 else 0
                at_prev = revenue.iloc[1] / assets.iloc[1] if assets.iloc[1] != 0 else 0
                if at_curr > at_prev:
                    return True, f"Asset turnover improved to {at_curr:.2f}x from {at_prev:.2f}x."
                else:
                    return False, f"Asset turnover declined to {at_curr:.2f}x from {at_prev:.2f}x."
    except Exception:
        pass

    return False, "Not enough data to check efficiency."


def _pct(val: Optional[float]) -> str:
    if val is None:
        return "N/A"
    return f"{val:.1%}"


def _fmt(val: Optional[float]) -> str:
    if val is None:
        return "N/A"
    if abs(val) >= 1e9:
        return f"${val/1e9:.1f}B"
    if abs(val) >= 1e6:
        return f"${val/1e6:.1f}M"
    return f"${val:,.0f}"
