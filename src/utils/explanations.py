"""
Plain English explanation engine.
Translates every metric into a sentence anyone can understand.
"""

from typing import Optional, Dict, Any


def explain_metric(metric: str, value: Optional[float], peer_avg: Optional[float] = None,
                   is_pct: bool = False) -> str:
    """Generate a plain-English explanation for a given metric value."""

    explanations = {
        "pe_ttm": lambda v, p: (
            f"The stock costs {v:.0f} times its earnings. "
            + (f"Peers cost {p:.0f}x — you're paying {'more' if v > p else 'less'} than average." if p else "")
        ),
        "pe_forward": lambda v, p: (
            f"Based on expected future earnings, the stock costs {v:.0f} times earnings. "
            + (f"Peers trade at {p:.0f}x forward." if p else "")
        ),
        "eps_ttm": lambda v, p: (
            f"The company earned ${v:.2f} per share over the last 12 months. "
            + (f"Peers average ${p:.2f}." if p else "")
        ),
        "peg_ratio": lambda v, p: (
            f"PEG of {v:.1f} — "
            + ("the stock looks undervalued when you factor in its growth rate." if v < 1
               else "the stock looks fairly valued relative to its growth." if v < 1.5
               else "the stock may be expensive even after accounting for growth.")
        ),
        "pb_ratio": lambda v, p: (
            f"The stock trades at {v:.1f} times its book value (accounting value of assets). "
            + (f"Peers trade at {p:.1f}x book." if p else "")
        ),
        "ps_ratio": lambda v, p: (
            f"You pay ${v:.1f} for every $1 of the company's sales. "
            + (f"Peers trade at {p:.1f}x sales." if p else "")
        ),
        "ev_ebitda": lambda v, p: (
            f"Enterprise value is {v:.0f} times EBITDA — "
            + ("this is a relatively low valuation." if v < 10
               else "this is a moderate valuation." if v < 15
               else "this is a premium valuation.")
        ),
        "roe": lambda v, p: (
            f"For every $100 of shareholder money, the company generates ${v*100:.0f} in profit. "
            + ("This is excellent." if v > 0.20
               else "This is good." if v > 0.15
               else "This is below average." if v < 0.10
               else "This is decent.")
        ),
        "roic": lambda v, p: (
            f"For every $100 invested in the business (by shareholders and lenders), it generates ${v*100:.0f} in profit. "
            + ("This is exceptional." if v > 0.15
               else "This is healthy." if v > 0.10
               else "This is below average.")
        ),
        "gross_margin": lambda v, p: (
            f"Out of every $100 of revenue, ${v*100:.0f} is profit after direct costs. "
            + ("This is very high — the company has strong pricing power." if v > 0.50
               else "This is healthy." if v > 0.30
               else "This is on the lower side — the business may have thin margins.")
        ),
        "operating_margin": lambda v, p: (
            f"After paying for operations, ${v*100:.0f} of every $100 in revenue is profit. "
            + ("The business is very efficient." if v > 0.20 else "This is decent.")
        ),
        "net_margin": lambda v, p: (
            f"After all expenses, the company keeps ${v*100:.0f} as profit from every $100 in revenue. "
            + ("This is excellent profitability." if v > 0.15
               else "This is good." if v > 0.10
               else "This is tight — not much room for error." if v < 0.05
               else "This is moderate.")
        ),
        "revenue_growth": lambda v, p: (
            f"Revenue {'grew' if v >= 0 else 'shrank'} by {abs(v)*100:.0f}% compared to last year. "
            + ("This is explosive growth." if v > 0.30
               else "This is strong growth." if v > 0.15
               else "This is steady growth." if v > 0.05
               else "Growth has stalled." if v >= 0
               else "The business is shrinking.")
        ),
        "earnings_growth": lambda v, p: (
            f"Profit per share {'grew' if v >= 0 else 'fell'} by {abs(v)*100:.0f}% over the last year. "
            + ("Profits are surging." if v > 0.25 else "Profits are growing well." if v > 0.10
               else "Profit growth is modest." if v >= 0 else "Profits are declining.")
        ),
        "debt_to_equity": lambda v, p: (
            f"For every $100 of shareholder equity, the company owes ${v:.0f} in debt. "
            + ("Debt is very low — the company is conservatively financed." if v < 30
               else "Debt is manageable." if v < 100
               else "Debt is higher than ideal." if v < 200
               else "Debt is very high — this adds significant risk.")
        ),
        "current_ratio": lambda v, p: (
            f"The company has ${v:.1f} in short-term assets for every $1 in short-term bills. "
            + ("It can easily pay its near-term obligations." if v > 2
               else "It has enough to cover near-term bills." if v > 1.5
               else "It may struggle with near-term bills." if v < 1
               else "It can cover its bills but not by a wide margin.")
        ),
        "beta": lambda v, p: (
            f"This stock moves {v:.1f}x as much as the overall market. "
            + ("Expect big swings both up and down — it's volatile." if v > 1.5
               else "It's more volatile than average." if v > 1.2
               else "It moves roughly in line with the market." if v > 0.8
               else "It's less volatile than the market — steadier but may lag in rallies.")
        ),
        "fcf": lambda v, p: (
            f"The company generates {_fmt_short(v)} in free cash flow — real money after all expenses and investments. "
            + ("This is a cash-generating machine." if v and v > 10e9
               else "This gives the company options: invest, acquire, or return cash to shareholders.")
        ),
        "dividend_yield": lambda v, p: (
            f"The dividend pays {v*100:.1f}% per year. "
            + ("This is a solid income." if v and v > 0.03
               else "This is a modest income stream." if v and v > 0.01
               else "The dividend is small — this is not an income investment.")
            if v and v > 0
            else "This company does not pay a dividend — it reinvests all profits for growth."
        ),
        "market_cap": lambda v, p: (
            f"The total company value is {_fmt_short(v)}. "
            + ("This is a mega-cap — one of the largest companies in the world." if v and v > 200e9
               else "This is a large, established company." if v and v > 10e9
               else "This is a mid-size company — more growth potential but more risk." if v and v > 2e9
               else "This is a smaller company — higher growth potential but higher risk.")
        ),
        "52w_position": lambda v, p: (
            f"The stock has risen {v:.0f}% from its 52-week low. "
            + ("It's near the top of its yearly range." if v and v > 80
               else "It's well above its yearly low." if v and v > 40
               else "It's closer to its yearly low than its high.")
        ),
        "interest_coverage": lambda v, p: (
            f"The company earns {v:.1f}x more than it needs to cover its interest payments. "
            + ("It can very comfortably service its debt." if v and v > 10
               else "It can comfortably cover its interest." if v and v > 5
               else "It can cover interest but not by much." if v and v > 2
               else "It struggles to cover interest — this is a red flag.")
        ),
        "ev_revenue": lambda v, p: (
            f"Enterprise value is {v:.1f} times revenue. "
            + ("A low multiple — you're not paying much for each dollar of sales." if v and v < 2
               else "A moderate multiple." if v and v < 5
               else "A high multiple — the market expects strong growth.")
        ),
        "payout_ratio": lambda v, p: (
            f"The company pays out {v*100:.0f}% of its earnings as dividends. "
            + ("The dividend is well covered by earnings — it's safe." if v and v < 0.60
               else "The dividend is safe but leaves less room for growth." if v and v < 0.80
               else "The dividend may not be sustainable — the company pays out nearly all its earnings.")
        ),
        "roa": lambda v, p: (
            f"For every $100 of assets, the company generates ${v*100:.0f} in profit. "
            + ("This is excellent asset efficiency." if v and v > 0.10
               else "This is good." if v and v > 0.05
               else "This is below average — the company may have too many assets for its profit level.")
        ),
    }

    if metric in explanations:
        return explanations[metric](value, peer_avg)
    return f"The current value is {value}."


def _fmt_short(val: Optional[float]) -> str:
    if val is None:
        return "N/A"
    if abs(val) >= 1e12:
        return f"${val/1e12:.1f}T"
    if abs(val) >= 1e9:
        return f"${val/1e9:.1f}B"
    if abs(val) >= 1e6:
        return f"${val/1e6:.1f}M"
    return f"${val:,.0f}"


def metric_label(metric: str) -> str:
    """Return a human-readable label for a metric key."""
    labels = {
        "pe_ttm": "P/E Ratio (TTM)",
        "pe_forward": "Forward P/E",
        "eps_ttm": "Earnings Per Share (TTM)",
        "peg_ratio": "PEG Ratio",
        "pb_ratio": "Price to Book",
        "ps_ratio": "Price to Sales",
        "ev_ebitda": "EV / EBITDA",
        "ev_revenue": "EV / Revenue",
        "roe": "Return on Equity",
        "roic": "Return on Invested Capital",
        "roa": "Return on Assets",
        "gross_margin": "Gross Margin",
        "operating_margin": "Operating Margin",
        "net_margin": "Net Margin",
        "revenue_growth": "Revenue Growth (YoY)",
        "earnings_growth": "Earnings Growth (YoY)",
        "debt_to_equity": "Debt to Equity",
        "current_ratio": "Current Ratio",
        "quick_ratio": "Quick Ratio",
        "interest_coverage": "Interest Coverage",
        "beta": "Beta (Volatility)",
        "fcf": "Free Cash Flow",
        "dividend_yield": "Dividend Yield",
        "payout_ratio": "Payout Ratio",
        "market_cap": "Market Cap",
        "52w_position": "52-Week Position",
        "graham_number": "Graham Fair Value",
    }
    return labels.get(metric, metric.replace("_", " ").title())


def format_metric_value(metric: str, value: Optional[float]) -> str:
    """Format a metric value appropriately."""
    if value is None:
        return "N/A"

    pct_metrics = {
        "gross_margin", "operating_margin", "net_margin",
        "roe", "roic", "roa",
        "revenue_growth", "earnings_growth",
        "dividend_yield", "payout_ratio",
    }

    dollar_metrics = {
        "fcf", "market_cap", "graham_number",
    }

    per_share = {
        "eps_ttm",
    }

    if metric in pct_metrics:
        return f"{value * 100:.1f}%" if abs(value) < 10 else f"{value:.2f}"
    elif metric in dollar_metrics:
        return _fmt_short(value)
    elif metric in per_share:
        return f"${value:.2f}"
    elif metric in ("debt_to_equity",):
        return f"{value:.0f}%"
    else:
        return f"{value:.2f}"


def metrics_by_tier() -> Dict[str, list]:
    """Return metrics organized by display tier."""
    return {
        "valuation": ["pe_ttm", "pe_forward", "peg_ratio", "pb_ratio", "ps_ratio", "ev_ebitda"],
        "profitability": ["roe", "roic", "gross_margin", "operating_margin", "net_margin"],
        "growth": ["revenue_growth", "earnings_growth"],
        "health": ["debt_to_equity", "current_ratio", "interest_coverage"],
        "market": ["beta", "fcf", "dividend_yield", "market_cap"],
    }
