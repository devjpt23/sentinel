"""
Number and text formatting utilities.
"""

from typing import Optional


def fmt_large_number(val: Optional[float]) -> str:
    """Format a large number into human-readable form."""
    if val is None:
        return "N/A"
    if abs(val) >= 1e12:
        return f"${val/1e12:.1f}T"
    if abs(val) >= 1e9:
        return f"${val/1e9:.1f}B"
    if abs(val) >= 1e6:
        return f"${val/1e6:.1f}M"
    if abs(val) >= 1e3:
        return f"${val/1e3:.1f}K"
    return f"${val:,.0f}"


def fmt_pct(val: Optional[float], decimals: int = 1) -> str:
    """Format a decimal as a percentage string."""
    if val is None:
        return "N/A"
    return f"{val * 100:.{decimals}f}%"


def fmt_currency(val: Optional[float]) -> str:
    """Format a dollar amount."""
    if val is None:
        return "N/A"
    return f"${val:,.2f}"


def color_for_value(metric: str, value: Optional[float], peer: Optional[float] = None) -> str:
    """Return a hex color (green/yellow/red) for a metric value."""
    if value is None:
        return "#888888"

    # Metrics where lower is better
    lower_better = {"pe_ttm", "pe_forward", "peg_ratio", "pb_ratio", "ps_ratio",
                    "ev_ebitda", "ev_revenue", "debt_to_equity", "beta", "payout_ratio"}

    # Metrics where higher is better
    higher_better = {"eps_ttm", "roe", "roic", "roa", "gross_margin", "operating_margin",
                     "net_margin", "revenue_growth", "earnings_growth", "fcf",
                     "current_ratio", "quick_ratio", "interest_coverage", "dividend_yield"}

    # Thresholds per metric (good_value, bad_value) — if lower is better, inverted
    thresholds = {
        "pe_ttm": (15, 30),
        "peg_ratio": (1.0, 2.0),
        "debt_to_equity": (50, 150),
        "beta": (1.0, 1.8),
        "roe": (0.15, 0.05),
        "roic": (0.12, 0.06),
        "roa": (0.08, 0.03),
        "gross_margin": (0.50, 0.25),
        "operating_margin": (0.20, 0.08),
        "net_margin": (0.15, 0.03),
        "revenue_growth": (0.15, 0.03),
        "earnings_growth": (0.12, 0.0),
        "current_ratio": (2.0, 1.0),
        "interest_coverage": (8, 2),
        "dividend_yield": (0.03, 0.01),
        "payout_ratio": (0.40, 0.80),
    }

    if metric in thresholds:
        good, bad = thresholds[metric]
    else:
        return "#888888"

    if metric in lower_better:
        if value <= good:
            return "#00C853"
        elif value >= bad:
            return "#FF1744"
        return "#FFD600"
    elif metric in higher_better:
        if value >= good:
            return "#00C853"
        elif value <= bad:
            return "#FF1744"
        return "#FFD600"

    return "#888888"


def emoji_for_verdict(verdict: str) -> str:
    """Return emoji for a verdict label."""
    verdict = verdict.lower()
    if verdict in ("strong", "undervalued", "low", "safe"):
        return "🟢"
    elif verdict in ("moderate", "fair", "medium", "grey"):
        return "🟡"
    elif verdict in ("weak", "overvalued", "high", "distress", "caution"):
        return "🔴"
    return "⚪"
