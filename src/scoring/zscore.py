"""
Altman Z-Score implementation.
Predicts bankruptcy risk within 2 years.
"""

from typing import Dict, Any, Optional, Tuple


def compute_altman_zscore(data: Dict[str, Any]) -> Tuple[Optional[float], str, str]:
    """Compute the Altman Z-Score (Z'' variant for non-manufacturing).

    Returns:
        (z_score, zone_label, explanation)
    """
    z_score, zone, explanation, _ = compute_altman_zscore_with_components(data)
    return z_score, zone, explanation


def compute_altman_zscore_with_components(data: Dict[str, Any]) -> Tuple[Optional[float], str, str, Dict[str, Optional[float]]]:
    """Compute the Altman Z-Score with individual X components.

    Returns:
        (z_score, zone_label, explanation, {x1, x2, x3, x4})
    """
    statements = data.get("statements", {})
    balance = statements.get("balance")
    income = statements.get("income")
    market = data.get("market", {})

    components: Dict[str, Optional[float]] = {"x1": None, "x2": None, "x3": None, "x4": None}

    try:
        if balance is None or balance.empty:
            return None, "Unknown", "Not enough data to calculate bankruptcy risk.", components

        # X1 = Working Capital / Total Assets
        wc = _get_latest(balance, "Working Capital")
        if wc is None:
            ca = _get_latest(balance, "Current Assets")
            cl = _get_latest(balance, "Current Liabilities")
            wc = (ca - cl) if ca is not None and cl is not None else None

        ta = _get_latest(balance, "Total Assets")
        x1 = wc / ta if wc is not None and ta and ta != 0 else 0
        components["x1"] = round(x1, 4)

        # X2 = Retained Earnings / Total Assets
        re_val = _get_latest(balance, "Retained Earnings")
        x2 = re_val / ta if re_val is not None and ta and ta != 0 else 0
        components["x2"] = round(x2, 4)

        # X3 = EBIT / Total Assets
        ebit = _get_latest(income, "EBIT") or _get_latest(income, "Operating Income")
        x3 = ebit / ta if ebit is not None and ta and ta != 0 else 0
        components["x3"] = round(x3, 4)

        # X4 = Market Value of Equity / Total Liabilities
        mv_equity = market.get("market_cap")
        tl = _get_latest(balance, "Total Liabilities")
        x4 = mv_equity / tl if mv_equity and tl and tl != 0 else 0
        components["x4"] = round(x4, 4)

        # Z'' formula (non-manufacturing): 6.56X1 + 3.26X2 + 6.72X3 + 1.05X4
        z = 6.56 * x1 + 3.26 * x2 + 6.72 * x3 + 1.05 * x4

        # Interpret
        if z > 2.6:
            zone = "Safe"
            explanation = "This company has a very low risk of financial distress based on its balance sheet strength."
        elif z > 1.1:
            zone = "Grey"
            explanation = "This company falls in a middle zone — not in immediate danger, but worth monitoring."
        else:
            zone = "Distress"
            explanation = "This company shows warning signs of potential financial trouble based on its balance sheet."

        return round(z, 2), zone, explanation, components

    except Exception:
        return None, "Unknown", "Could not calculate bankruptcy risk due to insufficient data.", components


def compute_zscore_normalized(z_score: Optional[float]) -> int:
    """Map Z-Score to 0-100 normalized scale."""
    if z_score is None:
        return 50  # neutral when unknown

    # Map: Z > 3.0 = 100, Z < 0 = 0
    normalized = min(100, max(0, (z_score / 3.0) * 100))
    return round(normalized)


def _get_latest(df, keyword: str) -> Optional[float]:
    """Get the latest value for a matching row label."""
    if df is None or df.empty:
        return None
    for label in df.index:
        if keyword.lower() in str(label).lower():
            vals = df.loc[label].dropna()
            if not vals.empty:
                return float(vals.iloc[0])
    return None
