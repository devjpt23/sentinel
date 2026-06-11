"""
PDF Report Generator.
Creates a one-page fundamental analysis summary using fpdf2.
"""

from fpdf import FPDF
from typing import Dict, Any

# Paths to Carlito font (Calibri-equivalent, with full Unicode support)
_FONT_DIR = "/usr/share/fonts/google-carlito-fonts"
_FONT_REGULAR = f"{_FONT_DIR}/Carlito-Regular.ttf"
_FONT_BOLD = f"{_FONT_DIR}/Carlito-Bold.ttf"


def _sanitize(text: str) -> str:
    """Replace Unicode characters that may not render in any font with ASCII equivalents."""
    replacements = {
        "—": "--",   # em dash
        "–": "--",   # en dash
        "‘": "'",    # left single quote
        "’": "'",    # right single quote
        "“": '"',    # left double quote
        "”": '"',    # right double quote
        "…": "...",  # ellipsis
        " ": " ",    # non-breaking space
    }
    for uni, ascii_replacement in replacements.items():
        text = text.replace(uni, ascii_replacement)
    return text


def generate_pdf_report(
    ticker: str,
    data: Dict[str, Any],
    health_score: int, health_verdict: str,
    price_verdict: str, price_short: str,
    intrinsic_score: int, intrinsic_verdict: str,
    risk_label: str, risk_summary: str,
    story: str,
    red_flags_count: int,
) -> bytes:
    """Generate a one-page PDF fundamental analysis report."""

    pdf = FPDF(orientation="P", unit="mm", format="A4")
    pdf.set_auto_page_break(auto=True, margin=15)

    # Register Unicode-capable font
    pdf.add_font("Carlito", "", _FONT_REGULAR)
    pdf.add_font("Carlito", "B", _FONT_BOLD)

    pdf.add_page()

    company = data.get("company", {})
    market = data.get("market", {})
    name = company.get("name", ticker)
    price = market.get("price")

    # ─── Colors ───
    DARK_BG = (13, 17, 23)
    CARD_BG = (22, 27, 34)
    BLUE = (88, 166, 255)
    GREY = (139, 148, 158)
    WHITE = (201, 209, 217)

    # ─── Header ───
    pdf.set_fill_color(*DARK_BG)
    pdf.rect(0, 0, 210, 35, "F")

    pdf.set_font("Carlito", "B", 20)
    pdf.set_text_color(*WHITE)
    pdf.set_xy(12, 8)
    pdf.cell(0, 10, _sanitize(f"{name} ({ticker})"), new_x="LMARGIN", new_y="NEXT")

    pdf.set_font("Carlito", "", 10)
    pdf.set_text_color(*GREY)
    pdf.set_xy(12, 18)
    sector_info = f"{company.get('sector', '')}  •  {company.get('industry', '')}"
    if price:
        sector_info += f"  •  ${price:.2f}"
    pdf.cell(0, 6, sector_info, new_x="LMARGIN", new_y="NEXT")

    # ─── Big 4 Cards ───
    card_y = 40
    card_w = 44
    card_h = 38
    gap = 3
    start_x = 12

    cards = [
        ("HEALTH", str(health_score), health_verdict, _score_color_rgb(health_score)),
        ("PRICE", price_verdict, price_short[:40], _score_color_rgb(70 if price_verdict in ("Undervalued", "Slightly Undervalued") else 50 if price_verdict == "Fair" else 30)),
        ("INTRINSIC", str(intrinsic_score), intrinsic_verdict, _score_color_rgb(intrinsic_score)),
        ("RISK", risk_label, risk_summary[:40], _score_color_rgb(70 if risk_label == "Low" else 50 if risk_label == "Medium" else 30)),
    ]

    for i, (label, value, sub, color) in enumerate(cards):
        x = start_x + i * (card_w + gap)
        pdf.set_fill_color(*CARD_BG)
        pdf.rect(x, card_y, card_w, card_h, "F")

        pdf.set_font("Carlito", "B", 7)
        pdf.set_text_color(*GREY)
        pdf.set_xy(x + 3, card_y + 3)
        pdf.cell(card_w - 6, 4, label, align="C")

        pdf.set_font("Carlito", "B", 16)
        pdf.set_text_color(*color)
        pdf.set_xy(x + 3, card_y + 10)
        pdf.cell(card_w - 6, 8, str(value), align="C")

        pdf.set_font("Carlito", "", 7)
        pdf.set_text_color(*GREY)
        pdf.set_xy(x + 3, card_y + 22)
        pdf.cell(card_w - 6, 12, _sanitize(sub), align="C")

    # ─── Story ───
    pdf.set_fill_color(*CARD_BG)
    story_y = card_y + card_h + 8
    pdf.rect(12, story_y, 186, 28, "F")

    pdf.set_font("Carlito", "B", 9)
    pdf.set_text_color(*BLUE)
    pdf.set_xy(16, story_y + 3)
    pdf.cell(0, 5, "THE STORY", new_x="LMARGIN", new_y="NEXT")

    pdf.set_font("Carlito", "", 8)
    pdf.set_text_color(*WHITE)
    pdf.set_xy(16, story_y + 10)
    pdf.multi_cell(178, 4, _sanitize(story[:400]))

    # ─── Key Metrics ───
    metrics = [
        ("P/E (TTM)", data.get("valuation", {}).get("pe_ttm"), "x"),
        ("Forward P/E", data.get("valuation", {}).get("pe_forward"), "x"),
        ("PEG Ratio", data.get("valuation", {}).get("peg_ratio"), ""),
        ("ROE", data.get("profitability", {}).get("roe"), "%"),
        ("Net Margin", data.get("profitability", {}).get("net_margin"), "%"),
        ("Revenue Growth", data.get("growth", {}).get("revenue_growth_yoy"), "%"),
        ("D/E Ratio", data.get("health", {}).get("debt_to_equity"), "%"),
        ("Beta", market.get("beta"), ""),
        ("Market Cap", market.get("market_cap"), "$"),
        ("FCF", data.get("health", {}).get("fcf"), "$"),
        ("Div Yield", data.get("per_share", {}).get("dividend_yield"), "%"),
        ("EPS (TTM)", data.get("per_share", {}).get("eps_ttm"), "$"),
    ]

    metrics_y = story_y + 36
    pdf.set_font("Carlito", "B", 9)
    pdf.set_text_color(*BLUE)
    pdf.set_xy(12, metrics_y)
    pdf.cell(0, 5, "KEY METRICS", new_x="LMARGIN", new_y="NEXT")

    col_w = 62
    row_h = 8
    for i, (label, val, unit) in enumerate(metrics):
        if val is None:
            continue
        col = i % 3
        row = i // 3
        x = 12 + col * col_w
        y = metrics_y + 8 + row * row_h

        pdf.set_fill_color(*CARD_BG)
        pdf.rect(x, y, col_w - 2, row_h - 1, "F")

        formatted = _fmt_metric(val, unit)
        pdf.set_font("Carlito", "B", 7)
        pdf.set_text_color(*WHITE)
        pdf.set_xy(x + 2, y + 1)
        pdf.cell(col_w - 4, 3, f"{label}: {formatted}")

    # ─── Footer ───
    pdf.set_font("Carlito", "", 7)
    pdf.set_text_color(*GREY)
    pdf.set_y(-20)

    risk_text = f"Risk: {risk_label}"
    if red_flags_count > 0:
        risk_text += f"  |  {red_flags_count} flag{'s' if red_flags_count > 1 else ''}"

    pdf.cell(0, 4, "Sentinel Fundamental Analysis Report", align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.cell(0, 4, risk_text + "  |  Not financial advice. Do your own research.", align="C")

    return bytes(pdf.output())


def _score_color_rgb(score: int) -> tuple:
    if score >= 70:
        return (0, 200, 83)
    elif score >= 40:
        return (255, 214, 0)
    return (255, 23, 68)


def _fmt_metric(val: float, unit: str) -> str:
    if unit == "%":
        if abs(val) < 1:
            return f"{val*100:.1f}%"
        return f"{val:.0f}%"
    elif unit == "$":
        if abs(val) >= 1e12:
            return f"${val/1e12:.1f}T"
        if abs(val) >= 1e9:
            return f"${val/1e9:.1f}B"
        if abs(val) >= 1e6:
            return f"${val/1e6:.0f}M"
        return f"${val:,.0f}"
    elif unit == "x":
        return f"{val:.1f}x"
    return f"{val:.2f}"
