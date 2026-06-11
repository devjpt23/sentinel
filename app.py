"""
Sentinel — Fundamental Analysis Dashboard
Phase 1+2: Big 3 Cards + Story + Key Numbers + Peer Context

A stock analysis tool that ANYONE can understand.
"""

import streamlit as st
import yfinance as yf
from concurrent.futures import ThreadPoolExecutor
from typing import Optional, Dict, Any, List, Tuple

from src.data.fetcher import fetch_company_data, fetch_peers, fetch_peer_metrics, compute_peer_averages
from src.data.fetcher import fetch_macro_context, fetch_analyst_data, fetch_institutional_data
from src.data.fetcher import fetch_top_movers, fetch_market_news, fetch_market_indices
from src.data.watchlist_db import init_db, load_watchlist, add_ticker as db_add_ticker, remove_ticker as db_remove_ticker, clear_watchlist as db_clear_watchlist
from src.scoring.health import compute_health_score
from src.scoring.zscore import compute_altman_zscore
from src.scoring.valuation import compute_price_verdict
from src.scoring.intrinsic import compute_intrinsic_worth
from src.scoring.risk import compute_risk_assessment, compute_red_flags
from src.scoring.common import score_to_color, score_to_emoji
from src.utils.explanations import explain_metric, metric_label, format_metric_value, metrics_by_tier
from src.utils.formatters import fmt_large_number, color_for_value
from src.display.deep_dive import render_financial_statements, render_fscore_breakdown, render_zscore_breakdown, render_dcf_model
from src.display.live_price import render_live_ticker
from src.display.sector_search import render_sector_search
from src.display.macro_strip import render_macro_strip
from src.display.sentiment import analyze_news_sentiment, render_sentiment_meter, render_analyst_consensus, render_institutional_activity

# ─── Page Config ───────────────────────────────────────────
st.set_page_config(
    page_title="Sentinel — Fundamental Analysis",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─── Database Init ──────────────────────────────────────────
init_db()

# ─── Session State ──────────────────────────────────────────
if "watchlist" not in st.session_state:
    st.session_state.watchlist = load_watchlist()
if "theme" not in st.session_state:
    st.session_state.theme = "dark"

# ─── Theme CSS ──────────────────────────────────────────────
theme = st.session_state.theme
if theme == "light":
    bg = "#FFFFFF"; card_bg = "#F6F8FA"; border = "#D0D7DE"
    text = "#1F2328"; muted = "#656D76"; accent = "#0969DA"
    hr_color = "#D0D7DE"; flag_danger_bg = "#FFEBE9"; flag_warn_bg = "#FFF8C5"
    input_bg = "#F6F8FA"
else:
    bg = "#0D1117"; card_bg = "#161B22"; border = "#30363D"
    text = "#C9D1D9"; muted = "#8B949E"; accent = "#58A6FF"
    hr_color = "#30363D"; flag_danger_bg = "#2D1518"; flag_warn_bg = "#2D2510"
    input_bg = "#161B22"

st.markdown(f"""
<style>
    /* Base theme */
    .stApp {{
        background-color: {bg};
        color: {text};
    }}

    /* Sidebar */
    [data-testid="stSidebar"] {{
        background-color: {card_bg};
        border-right: 1px solid {border};
    }}
    [data-testid="stSidebar"] * {{
        color: {text};
    }}

    /* Cards */
    .metric-card {{
        background: {card_bg};
        border: 1px solid {border};
        border-radius: 12px;
        padding: 24px;
        text-align: center;
        margin: 4px;
    }}
    .metric-card h3 {{
        color: {muted};
        font-size: 0.85rem;
        text-transform: uppercase;
        letter-spacing: 0.05em;
        margin: 0 0 8px 0;
    }}
    .metric-card .score {{
        font-size: 3rem;
        font-weight: 700;
        margin: 4px 0;
        line-height: 1.1;
    }}
    .metric-card .verdict {{
        font-size: 1.1rem;
        font-weight: 600;
        margin: 4px 0;
    }}
    .metric-card .detail {{
        color: {muted};
        font-size: 0.8rem;
        line-height: 1.4;
        margin-top: 8px;
    }}

    /* Key Number cards */
    .key-card {{
        background: {card_bg};
        border: 1px solid {border};
        border-radius: 10px;
        padding: 16px 20px;
        margin: 4px;
        height: 100%;
        cursor: help;
    }}
    .key-card .metric-name {{
        color: {muted};
        font-size: 0.75rem;
        text-transform: uppercase;
        letter-spacing: 0.05em;
    }}
    .key-card .metric-value {{
        font-size: 1.5rem;
        font-weight: 700;
        margin: 4px 0;
    }}
    .key-card .metric-explanation {{
        color: {muted};
        font-size: 0.8rem;
        line-height: 1.4;
        margin-top: 4px;
    }}

    /* Story box */
    .story-box {{
        background: {card_bg};
        border-left: 4px solid {accent};
        border-radius: 8px;
        padding: 20px 24px;
        margin: 16px 0;
        font-size: 1.05rem;
        line-height: 1.6;
        color: {text};
    }}

    /* Company header */
    .company-header {{
        margin-bottom: 8px;
    }}
    .company-header h1 {{
        font-size: 2rem;
        margin-bottom: 4px;
    }}
    .company-header .meta {{
        color: {muted};
        font-size: 0.9rem;
    }}
    .company-header .description {{
        color: {muted};
        font-size: 0.85rem;
        margin-top: 10px;
        line-height: 1.5;
        max-width: 900px;
    }}

    /* Section title */
    .section-title {{
        color: {accent};
        font-size: 1.1rem;
        font-weight: 600;
        margin: 24px 0 12px 0;
        padding-bottom: 8px;
        border-bottom: 1px solid {border};
    }}

    /* Peer table */
    .peer-table {{
        width: 100%;
        border-collapse: collapse;
        font-size: 0.85rem;
    }}
    .peer-table th {{
        color: {muted};
        font-weight: 600;
        text-align: left;
        padding: 8px 12px;
        border-bottom: 1px solid {border};
    }}
    .peer-table td {{
        padding: 8px 12px;
        border-bottom: 1px solid {border};
    }}

    /* Red flags */
    .flag-danger {{
        background: {flag_danger_bg};
        border-left: 4px solid #FF1744;
        border-radius: 6px;
        padding: 16px;
        margin: 8px 0;
    }}
    .flag-warning {{
        background: {flag_warn_bg};
        border-left: 4px solid #FFD600;
        border-radius: 6px;
        padding: 16px;
        margin: 8px 0;
    }}
    .flag-title {{
        font-weight: 700;
        font-size: 0.9rem;
        margin-bottom: 4px;
    }}
    .flag-danger .flag-title {{ color: #FF6B7A; }}
    .flag-warning .flag-title {{ color: #B08800; }}
    .flag-body {{ color: {text}; font-size: 0.85rem; line-height: 1.4; }}

    /* Sparklines */
    .sparkline-label {{
        color: {muted};
        font-size: 0.7rem;
        text-transform: uppercase;
        margin-bottom: 4px;
    }}

    /* Tooltips */
    .tooltip-wrapper {{
        position: relative;
        display: inline-block;
        cursor: help;
    }}
    .tooltip-wrapper .tooltip-text {{
        visibility: hidden;
        width: 240px;
        background: {card_bg};
        border: 1px solid {accent};
        color: {text};
        text-align: left;
        border-radius: 8px;
        padding: 10px 14px;
        position: absolute;
        z-index: 9999;
        bottom: 125%;
        left: 50%;
        margin-left: -120px;
        font-size: 0.8rem;
        line-height: 1.4;
        opacity: 0;
        transition: opacity 0.2s;
        pointer-events: none;
    }}
    .tooltip-wrapper:hover .tooltip-text {{
        visibility: visible;
        opacity: 1;
    }}

    /* Watchlist card */
    .watchlist-card {{
        background: {card_bg};
        border: 1px solid {border};
        border-radius: 10px;
        padding: 16px 20px;
        margin: 6px 0;
        display: flex;
        align-items: center;
        justify-content: space-between;
    }}
    .watchlist-card:hover {{
        border-color: {accent};
    }}

    /* Macro strip cards */
    .macro-card {{
        background: {card_bg};
        border: 1px solid {border};
        border-radius: 10px;
        padding: 14px 12px;
        text-align: center;
        height: 100%;
        cursor: help;
    }}
    .macro-card .macro-icon {{
        font-size: 1.3rem;
        margin-bottom: 4px;
    }}
    .macro-card .macro-label {{
        color: {muted};
        font-size: 0.7rem;
        text-transform: uppercase;
        letter-spacing: 0.05em;
        margin-bottom: 4px;
    }}
    .macro-card .macro-value {{
        font-size: 1.2rem;
        font-weight: 700;
        margin: 2px 0;
    }}
    .macro-card .macro-verdict {{
        font-size: 0.75rem;
        font-weight: 600;
        margin-top: 2px;
    }}

    /* Institutional holder cards */
    .inst-card {{
        background: {card_bg};
        border: 1px solid {border};
        border-radius: 8px;
        padding: 14px 12px;
        text-align: center;
        height: 100%;
    }}
    .inst-card .inst-name {{
        color: {text};
        font-size: 0.75rem;
        font-weight: 600;
        margin-bottom: 4px;
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
    }}
    .inst-card .inst-held {{
        color: {muted};
        font-size: 0.7rem;
        margin-bottom: 4px;
    }}
    .inst-card .inst-change {{
        font-size: 0.8rem;
        font-weight: 600;
    }}

    /* Analyst section */
    .analyst-section {{
        background: {card_bg};
        border: 1px solid {border};
        border-radius: 12px;
        padding: 20px 24px;
        margin: 8px 0;
    }}

    /* Details expander */
    .streamlit-expanderHeader {{
        background: {card_bg};
        border: 1px solid {border};
        border-radius: 8px;
        color: {accent};
        font-weight: 600;
    }}

    /* Search bar */
    [data-testid="stTextInput"] input {{
        background: {input_bg};
        border: 1px solid {border};
        border-radius: 8px;
        color: {text};
        font-size: 1rem;
        padding: 12px 16px;
    }}
    [data-testid="stTextInput"] input:focus {{
        border-color: {accent};
        box-shadow: 0 0 0 2px rgba(88, 166, 255, 0.2);
    }}

    /* Hide Streamlit default elements */
    #MainMenu {{ visibility: hidden; }}
    footer {{ visibility: hidden; }}

    /* Divider */
    hr {{
        border-color: {hr_color};
        margin: 20px 0;
    }}

    /* Print-friendly */
    @media print {{
        .stApp {{ background: white !important; color: black !important; }}
        [data-testid="stSidebar"] {{ display: none !important; }}
        [data-testid="stHeader"] {{ display: none !important; }}
        .stButton {{ display: none !important; }}
        .stExpander {{ display: none !important; }}
        hr {{ display: none !important; }}
        .metric-card, .key-card, .story-box, .watchlist-card {{
            border: 1px solid #ccc !important;
            background: #f9f9f9 !important;
            break-inside: avoid;
        }}
    }}

    /* ── Watchlist Marquee ─────────────────────────── */
    .marquee-wrapper {{
        background: {card_bg};
        border-top: 1px solid {border};
        border-bottom: 1px solid {border};
        padding: 8px 0;
        margin: 0 0 16px 0;
        overflow: hidden;
        position: relative;
    }}
    .marquee-track {{
        display: flex;
        gap: 40px;
        animation: marquee-scroll 25s linear infinite;
        white-space: nowrap;
        width: max-content;
    }}
    .marquee-wrapper:hover .marquee-track {{
        animation-play-state: paused;
    }}
    @keyframes marquee-scroll {{
        0% {{ transform: translateX(0); }}
        100% {{ transform: translateX(-50%); }}
    }}
    .marquee-item {{
        display: inline-flex;
        align-items: center;
        gap: 8px;
        font-size: 0.85rem;
        flex-shrink: 0;
    }}
    .marquee-item .marquee-ticker {{
        font-weight: 700;
        color: {accent};
    }}
    .marquee-item .marquee-price {{
        color: {text};
        font-weight: 600;
    }}
    .marquee-item .marquee-change-up {{
        color: #00C853;
        font-weight: 600;
    }}
    .marquee-item .marquee-change-down {{
        color: #FF1744;
        font-weight: 600;
    }}

    /* ── Movers Table ──────────────────────────────── */
    .movers-table {{
        width: 100%;
        border-collapse: collapse;
        font-size: 0.85rem;
    }}
    .movers-table th {{
        color: {muted};
        font-weight: 600;
        text-align: left;
        padding: 6px 10px;
        border-bottom: 1px solid {border};
        font-size: 0.7rem;
        text-transform: uppercase;
        letter-spacing: 0.05em;
    }}
    .movers-table td {{
        padding: 8px 10px;
        border-bottom: 1px solid {border};
    }}
    .movers-table tr:hover td {{
        background: rgba(88, 166, 255, 0.05);
    }}
    .movers-table a {{
        color: {accent};
        text-decoration: none;
        font-weight: 600;
    }}
    .movers-table a:hover {{
        text-decoration: underline;
    }}

    /* ── Market News Card ──────────────────────────── */
    .news-item {{
        background: {card_bg};
        border: 1px solid {border};
        border-radius: 8px;
        padding: 12px 16px;
        margin: 4px 0;
        transition: border-color 0.2s;
    }}
    .news-item:hover {{
        border-color: {accent};
    }}
    .news-item a {{
        color: {accent};
        text-decoration: none;
        font-weight: 600;
        font-size: 0.9rem;
        line-height: 1.3;
    }}
    .news-item a:hover {{
        text-decoration: underline;
    }}
    .news-item .news-meta {{
        color: {muted};
        font-size: 0.7rem;
        margin-top: 4px;
    }}

    /* ── Indices Strip ─────────────────────────────── */
    .indices-strip {{
        display: flex;
        gap: 12px;
        margin: 8px 0 16px 0;
        flex-wrap: wrap;
    }}
    .index-card {{
        background: {card_bg};
        border: 1px solid {border};
        border-radius: 10px;
        padding: 12px 18px;
        text-align: center;
        flex: 1;
        min-width: 120px;
    }}
    .index-card .index-name {{
        color: {muted};
        font-size: 0.7rem;
        text-transform: uppercase;
        letter-spacing: 0.05em;
        margin-bottom: 4px;
    }}
    .index-card .index-price {{
        font-size: 1.3rem;
        font-weight: 700;
        color: {text};
    }}
    .index-card .index-change-up {{
        color: #00C853;
        font-weight: 600;
        font-size: 0.9rem;
    }}
    .index-card .index-change-down {{
        color: #FF1744;
        font-weight: 600;
        font-size: 0.9rem;
    }}
</style>
""", unsafe_allow_html=True)

# ─── Sidebar ───────────────────────────────────────────────
with st.sidebar:
    st.markdown(
        '<div style="text-align: center; padding: 20px 0 20px 0;">'
        '<h2 style="color: #58A6FF; margin: 0;">📊 Sentinel</h2>'
        '<p style="color: #8B949E; font-size: 0.8rem; margin-top: 4px;">Fundamental Analysis<br>Made Simple</p>'
        '</div>',
        unsafe_allow_html=True
    )

    st.markdown("### Navigation")
    nav_options = ["🏠 Dashboard", "📋 Watchlist", "🎯 Strategy Lab", "🔍 Sector Search", "ℹ️ About"]
    default_idx = st.session_state.pop("_nav_idx", 0)
    page = st.radio(
        "",
        nav_options,
        index=default_idx if 0 <= default_idx < len(nav_options) else 0,
        label_visibility="collapsed",
    )

    st.markdown("---")

    # Theme toggle
    theme_label = "🌙 Dark Mode" if st.session_state.theme == "dark" else "☀️ Light Mode"
    if st.button(theme_label, use_container_width=True):
        st.session_state.theme = "light" if st.session_state.theme == "dark" else "dark"
        st.rerun()

    # Watchlist count
    wl_count = len(st.session_state.watchlist)
    if wl_count > 0:
        st.markdown(f"📋 **{wl_count}** stock{'s' if wl_count > 1 else ''} watched")

    st.markdown("---")
    st.markdown(
        '<p style="color: #484F58; font-size: 0.7rem;">'
        'Data from Yahoo Finance. Not financial advice. '
        'Always do your own research before investing.'
        '</p>',
        unsafe_allow_html=True
    )


# ─── Helper: Build Headline Cards (4 cards) ──────────────────
def render_headline_cards(health_score: int, health_verdict: str,
                          price_score: int, price_verdict: str, price_short: str,
                          intrinsic_score: int, intrinsic_verdict: str, intrinsic_summary: str,
                          risk_score: int, risk_label: str, risk_summary: str):
    """Render the four main verdict cards."""
    cols = st.columns(4)

    with cols[0]:
        h_color = score_to_color(health_score)
        h_emoji = score_to_emoji(health_score)
        st.markdown(
            f'<div class="metric-card">'
            f'<h3>{h_emoji} Health</h3>'
            f'<div class="score" style="color: {h_color};">{health_score}</div>'
            f'<div class="verdict" style="color: {h_color};">out of 100</div>'
            f'<div class="detail">{health_verdict} — in good financial shape</div>'
            f'</div>',
            unsafe_allow_html=True
        )

    with cols[1]:
        p_color = score_to_color(price_score, low=35, high=65)
        p_emoji = score_to_emoji(price_score, low=35, high=65)
        st.markdown(
            f'<div class="metric-card">'
            f'<h3>{p_emoji} Price vs Peers</h3>'
            f'<div class="score" style="color: {p_color};">{price_verdict}</div>'
            f'<div class="verdict" style="color: {p_color};">Relative Value</div>'
            f'<div class="detail">{price_short}</div>'
            f'</div>',
            unsafe_allow_html=True
        )

    with cols[2]:
        i_color = score_to_color(intrinsic_score, low=35, high=65)
        i_emoji = score_to_emoji(intrinsic_score, low=35, high=65)
        st.markdown(
            f'<div class="metric-card">'
            f'<h3>{i_emoji} Intrinsic Worth</h3>'
            f'<div class="score" style="color: {i_color};">{intrinsic_verdict}</div>'
            f'<div class="verdict" style="color: {i_color};">Absolute Value</div>'
            f'<div class="detail">{intrinsic_summary}</div>'
            f'</div>',
            unsafe_allow_html=True
        )

    with cols[3]:
        r_color = score_to_color(risk_score)
        r_emoji = score_to_emoji(risk_score)
        st.markdown(
            f'<div class="metric-card">'
            f'<h3>{r_emoji} Risk</h3>'
            f'<div class="score" style="color: {r_color};">{risk_label}</div>'
            f'<div class="verdict" style="color: {r_color};">Risk Level</div>'
            f'<div class="detail">{risk_summary}</div>'
            f'</div>',
            unsafe_allow_html=True
        )


# ─── Helper: Build Story ───────────────────────────────────
def render_story(data: Dict[str, Any], health_verdict: str, price_verdict: str,
                 intrinsic_verdict: str, risk_label: str, red_flags: List,
                 macro_data: Optional[Dict[str, Any]] = None) -> str:
    """Generate and render the plain-English story paragraph.

    Optionally weaves in macro context when available.
    """
    company = data.get("company", {})
    name = company.get("name", "This company")
    health = data.get("health", {})
    growth = data.get("growth", {})

    parts = [f"{name} is"]

    # Health part
    if health_verdict == "Strong":
        parts.append("a financially strong company with healthy profits")
    elif health_verdict == "Moderate":
        parts.append("in decent financial shape, though not outstanding")
    else:
        parts.append("showing some financial strain")

    # Debt part
    de = health.get("debt_to_equity")
    if de is not None and de < 50:
        parts.append("and very low debt")
    elif de is not None and de < 100:
        parts.append("and manageable debt")
    elif de is not None:
        parts.append("though it carries significant debt")

    parts.append(".")

    # Price vs Peers
    if price_verdict in ("Undervalued", "Slightly Undervalued"):
        parts.append("Compared to similar companies, the stock looks reasonably priced")
    elif price_verdict == "Fair":
        parts.append("The stock trades in line with what similar companies command")
    elif price_verdict in ("Slightly Overvalued",):
        parts.append("The stock trades at a premium to similar companies")
    else:
        parts.append("The stock looks expensive compared to what similar companies cost")

    parts.append(".")

    # Intrinsic worth
    if intrinsic_verdict in ("Undervalued", "Slightly Undervalued"):
        parts.append("More importantly, the business itself appears to be worth more than the current stock price — conservative measures suggest genuine value here")
    elif intrinsic_verdict == "Fair":
        parts.append("The stock price roughly matches what the business is worth based on its earnings, cash flow, and assets")
    else:
        parts.append("However, the stock trades well above what the underlying business is worth by conservative measures — you're paying a premium that requires future growth to justify")

    parts.append(".")

    # Risk part
    if risk_label == "Low":
        parts.append("Risk appears low")
    elif risk_label == "Medium":
        parts.append("There are some risks to watch")
    else:
        parts.append("There are notable risks that deserve attention")
    parts.append(".")

    # Growth context
    rev_growth = growth.get("revenue_growth_yoy")
    if rev_growth is not None and rev_growth > 0.15:
        parts.append(f"Revenue is growing strongly at {rev_growth*100:.0f}% year over year.")
    elif rev_growth is not None and rev_growth > 0:
        parts.append(f"Revenue is growing at a steady {rev_growth*100:.0f}% pace.")
    elif rev_growth is not None:
        parts.append(f"Revenue declined {abs(rev_growth)*100:.0f}% — watch this trend.")

    # ── Macro context (NEW) ───────────────────────────────
    if macro_data:
        macro_parts = []
        sp500 = macro_data.get("sp500", {})
        vix = macro_data.get("vix", {})

        if sp500:
            trend = sp500.get("verdict", "")
            if trend == "Uptrend":
                macro_parts.append("The broader market is in an uptrend, which generally supports this stock's momentum")
            elif trend == "Downtrend":
                macro_parts.append("The broader market is in a downtrend, which creates headwinds even for strong companies")
            else:
                macro_parts.append("The broader market is choppy, so expect mixed signals")

        if vix:
            vix_val = vix.get("value")
            vix_verdict = vix.get("verdict", "")
            if vix_verdict == "Fearful":
                macro_parts.append(f"With the VIX at {vix_val:.0f}, expect larger-than-normal daily swings — this is a high-fear environment")
            elif vix_verdict == "Calm":
                macro_parts.append(f"With the VIX at {vix_val:.0f}, the market is unusually calm right now")

        if macro_parts:
            parts.extend(macro_parts)

    story = " ".join(parts)
    # Clean up duplicate periods
    story = story.replace("..", ".")
    return story


# ─── Helper: Render Key Numbers ────────────────────────────
def render_key_numbers(data: Dict[str, Any], peer_averages: Dict[str, Optional[float]]):
    """Render the Key Numbers section with metric cards."""
    tiers = metrics_by_tier()

    # Flatten to primary metrics we want to show
    primary_metrics = [
        # Valuation
        ("pe_ttm", data.get("valuation", {}).get("pe_ttm"), peer_averages.get("pe_ttm")),
        ("eps_ttm", data.get("per_share", {}).get("eps_ttm"), None),
        ("peg_ratio", data.get("valuation", {}).get("peg_ratio"), None),
        # Profitability
        ("roe", data.get("profitability", {}).get("roe"), peer_averages.get("roe")),
        ("net_margin", data.get("profitability", {}).get("net_margin"), peer_averages.get("net_margin")),
        ("roic", data.get("profitability", {}).get("roic"), peer_averages.get("roic")),
        # Growth
        ("revenue_growth", data.get("growth", {}).get("revenue_growth_yoy"), peer_averages.get("revenue_growth")),
        # Health
        ("debt_to_equity", data.get("health", {}).get("debt_to_equity"), peer_averages.get("debt_to_equity")),
        ("interest_coverage", data.get("health", {}).get("interest_coverage"), None),
        # Market
        ("beta", data.get("market", {}).get("beta"), None),
        ("fcf", data.get("health", {}).get("fcf"), None),
        ("market_cap", data.get("market", {}).get("market_cap"), None),
        ("dividend_yield", data.get("per_share", {}).get("dividend_yield"), peer_averages.get("dividend_yield")),
    ]

    # Filter out metrics with no value
    primary_metrics = [(m, v, p) for m, v, p in primary_metrics if v is not None]

    # Render in rows of 4
    for i in range(0, len(primary_metrics), 4):
        row_metrics = primary_metrics[i:i+4]
        cols = st.columns(len(row_metrics))

        for j, (metric, value, peer_val) in enumerate(row_metrics):
            label = metric_label(metric)
            formatted = format_metric_value(metric, value)
            color = color_for_value(metric, value, peer_val)
            explanation = explain_metric(metric, value, peer_val)

            with cols[j]:
                st.markdown(
                    f'<div class="key-card">'
                    f'<div class="metric-name">{label}</div>'
                    f'<div class="metric-value" style="color: {color};">{formatted}</div>'
                    f'<div class="metric-explanation">{explanation}</div>'
                    f'</div>',
                    unsafe_allow_html=True
                )


# ─── Helper: Render Peer Comparison ────────────────────────
def render_peer_comparison(data: Dict[str, Any], peer_data: Dict[str, Dict[str, Any]],
                           peer_averages: Dict[str, Optional[float]]):
    """Render peer comparison section."""
    if not peer_data:
        st.markdown('<p style="color: #8B949E;">No peer data available for comparison.</p>',
                    unsafe_allow_html=True)
        return

    company_name = data.get("company", {}).get("name", "This Stock")
    ticker = data.get("company", {}).get("ticker", "")

    valuation = data.get("valuation", {})
    profitability = data.get("profitability", {})
    health = data.get("health", {})
    growth = data.get("growth", {})

    # Build a clean comparison table
    rows = []
    metrics_for_table = [
        ("P/E (TTM)", valuation.get("pe_ttm"), peer_averages.get("pe_ttm"),
         lambda v, p: "🟢" if v and p and v < p * 0.9 else "🟡" if v and p and v < p * 1.2 else "🔴"),
        ("ROE", profitability.get("roe"), peer_averages.get("roe"),
         lambda v, p: "🟢" if v and p and v > p * 1.1 else "🟡" if v and p and v > p * 0.8 else "🔴"),
        ("Net Margin", profitability.get("net_margin"), peer_averages.get("net_margin"),
         lambda v, p: "🟢" if v and p and v > p * 1.1 else "🟡" if v and p and v > p * 0.8 else "🔴"),
        ("Revenue Growth", growth.get("revenue_growth_yoy"), peer_averages.get("revenue_growth"),
         lambda v, p: "🟢" if v and p and v > p * 1.2 else "🟡" if v and p and v > p * 0.5 else "🔴"),
        ("D/E Ratio", health.get("debt_to_equity"), peer_averages.get("debt_to_equity"),
         lambda v, p: "🟢" if v and p and v < p * 0.8 else "🟡" if v and p and v < p * 1.3 else "🔴"),
    ]

    company_short = company_name.split(" ")[0]
    peer_names = [peer_data[p].get("name", p) for p in peer_data]

    # Build rows
    rows_html = ""
    for label, val, peer, emoji_fn in metrics_for_table:
        v_str = format_metric_value_for_table(label, val)
        p_str = format_metric_value_for_table(label, peer)
        emoji = emoji_fn(val, peer) if val is not None and peer is not None else "⚪"
        rows_html += f"<tr><td>{label}</td><td><strong>{v_str}</strong></td><td>{p_str}</td><td>{emoji}</td></tr>"

    # Build full table — NO leading whitespace (indented HTML = code block in markdown)
    table_html = (
        f'<table class="peer-table">'
        f"<thead><tr><th>Metric</th><th>{company_short}</th><th>Peer Avg</th><th></th></tr></thead>"
        f"<tbody>{rows_html}"
        f'<tr><td colspan="4" style="color: #484F58; font-size: 0.75rem; padding-top: 12px;">'
        f"Compared against: {', '.join(peer_names[:6])}"
        f"</td></tr></tbody></table>"
    )
    st.markdown(table_html, unsafe_allow_html=True)


def format_metric_value_for_table(label: str, val: Optional[float]) -> str:
    """Format a metric value for table display."""
    if val is None:
        return "N/A"
    if "Margin" in label or "Growth" in label or "ROE" in label:
        return f"{val*100:.1f}%" if abs(val) < 10 else f"{val:.2f}"
    elif "D/E" in label:
        return f"{val:.0f}%"
    elif "P/E" in label:
        return f"{val:.1f}x"
    return f"{val:.2f}"


# ─── Helper: Render Red Flags ──────────────────────────────
def render_red_flags(red_flags: List[Tuple[str, str, str]]):
    """Render red flag alerts."""
    if not red_flags:
        st.markdown(
            '<div style="background: #162316; border-left: 4px solid #00C853; border-radius: 6px; padding: 16px; margin: 8px 0;">'
            '<div class="flag-title" style="color: #00C853;">✅ No Red Flags Detected</div>'
            '<div class="flag-body">No significant warning signs found in the data we analyzed. '
            "This doesn't mean the investment is risk-free — always do your own research.</div>"
            '</div>',
            unsafe_allow_html=True
        )
        return

    danger_flags = [f for f in red_flags if f[0] == "danger"]
    warning_flags = [f for f in red_flags if f[0] == "warning"]

    if danger_flags:
        st.markdown(
            f'<div style="color: #FF6B7A; font-weight: 700; font-size: 0.9rem; margin-bottom: 8px;">'
            f"⚠️ {len(danger_flags)} Serious Concern{'s' if len(danger_flags) > 1 else ''}"
            f'</div>',
            unsafe_allow_html=True
        )
        for _, title, body in danger_flags:
            st.markdown(
                f'<div class="flag-danger">'
                f'<div class="flag-title">🔴 {title}</div>'
                f'<div class="flag-body">{body}</div>'
                f'</div>',
                unsafe_allow_html=True
            )

    if warning_flags:
        if danger_flags:
            st.markdown("<br>", unsafe_allow_html=True)
        for _, title, body in warning_flags:
            st.markdown(
                f'<div class="flag-warning">'
                f'<div class="flag-title">🟡 {title}</div>'
                f'<div class="flag-body">{body}</div>'
                f'</div>',
                unsafe_allow_html=True
            )


# ─── Helper: Watchlist Marquee ───────────────────────────────
def render_watchlist_marquee():
    """Render a scrolling marquee of watchlist stocks with live prices.

    Fetches current price and daily change for each watchlist ticker
    and displays them in a continuously scrolling horizontal strip.
    Pausing on hover so users can click through.
    """
    watchlist = st.session_state.get("watchlist", [])
    if not watchlist:
        return

    items_html = []
    for ticker in watchlist:
        try:
            t = yf.Ticker(ticker)
            info = t.info or {}
            price = info.get("currentPrice") or info.get("regularMarketPrice")
            if price is None:
                # fallback: use fast_info
                try:
                    price = t.fast_info.get("lastPrice")
                except Exception:
                    pass
            change_pct = info.get("regularMarketChangePercent")
            if change_pct is None:
                prev_close = info.get("regularMarketPreviousClose") or info.get("previousClose")
                if price and prev_close and prev_close > 0:
                    change_pct = ((price - prev_close) / prev_close) * 100

            if price is None:
                continue

            change_class = "marquee-change-up" if (change_pct or 0) >= 0 else "marquee-change-down"
            change_sign = "+" if (change_pct or 0) >= 0 else ""
            change_str = f"{change_sign}{change_pct:.2f}%" if change_pct is not None else ""

            items_html.append(
                f'<span class="marquee-item">'
                f'<span class="marquee-ticker">{ticker}</span>'
                f'<span class="marquee-price">${price:.2f}</span>'
                f'<span class="{change_class}">{change_str}</span>'
                f'</span>'
            )
        except Exception:
            continue

    if not items_html:
        return

    # Duplicate items so the scroll loops seamlessly (CSS translates by -50%)
    track_items = items_html + items_html

    st.markdown(
        f'<div class="marquee-wrapper">'
        f'<div class="marquee-track">{" • ".join(track_items)}</div>'
        f'</div>',
        unsafe_allow_html=True,
    )


# ─── Helper: Render Market Indices Strip ──────────────────────
def render_indices_strip(indices: list[dict]):
    """Render a horizontal strip of major index cards showing current levels
    and daily changes.
    """
    if not indices:
        return

    cards = []
    for idx in indices:
        price = idx.get("price")
        change_pct = idx.get("change_pct")
        direction = idx.get("direction", "up")

        if price is None:
            continue

        # Format price: indices can be large (e.g. 42000 for DJIA)
        if price >= 10000:
            price_str = f"{price:,.0f}"
        elif price >= 1000:
            price_str = f"{price:,.1f}"
        else:
            price_str = f"{price:,.2f}"

        change_class = "index-change-up" if direction == "up" else "index-change-down"
        change_sign = "+" if direction == "up" else ""
        change_str = f"{change_sign}{change_pct:.2f}%" if change_pct is not None else ""

        cards.append(
            f'<div class="index-card">'
            f'<div class="index-name">{idx["emoji"]} {idx["name"]}</div>'
            f'<div class="index-price">{price_str}</div>'
            f'<div class="{change_class}">{change_str}</div>'
            f'</div>'
        )

    st.markdown(
        f'<div class="indices-strip">{"".join(cards)}</div>',
        unsafe_allow_html=True,
    )


# ─── Helper: Render Top Movers ────────────────────────────────
def render_top_movers(movers: list[dict]):
    """Render a table of the top 10 daily movers (by absolute % change).

    Each row shows the ticker (clickable), company name, price, and
    color-coded daily change.
    """
    if not movers:
        st.markdown(
            '<p style="color: #484F58; font-size: 0.85rem;">No mover data available right now.</p>',
            unsafe_allow_html=True,
        )
        return

    rows = []
    for i, m in enumerate(movers):
        ticker = m["ticker"]
        name = m.get("name", ticker)[:30]
        price = m.get("price")
        change_pct = m.get("change_pct", 0)
        direction = m.get("direction", "up")

        price_str = f"${price:.2f}" if price is not None else "—"
        change_color = "#00C853" if direction == "up" else "#FF1744"
        change_arrow = "▲" if direction == "up" else "▼"
        change_str = f"{change_arrow} {abs(change_pct):.2f}%"

        # Build a link that pre-fills the dashboard ticker search
        # Streamlit doesn't support real links to itself, so use a button-like link
        ticker_link = (
            f'<a href="?ticker={ticker}" target="_self" '
            f'onclick="window.location.href=window.location.pathname+\'?ticker={ticker}\';return false;">'
            f'{ticker}</a>'
        )

        rows.append(
            f'<tr>'
            f'<td style="width: 30px; color: #484F58; font-size: 0.75rem;">{i+1}</td>'
            f'<td>{ticker_link}</td>'
            f'<td style="color: #8B949E; font-size: 0.8rem;">{name}</td>'
            f'<td style="text-align: right;">{price_str}</td>'
            f'<td style="text-align: right; color: {change_color}; font-weight: 600;">{change_str}</td>'
            f'</tr>'
        )

    st.markdown(
        f'<table class="movers-table">'
        f'<thead><tr><th></th><th>Ticker</th><th>Company</th><th>Price</th><th>Change</th></tr></thead>'
        f'<tbody>{"".join(rows)}</tbody>'
        f'</table>',
        unsafe_allow_html=True,
    )


# ─── Helper: Render Market News ───────────────────────────────
def render_market_news_section(news_items: list[dict]):
    """Render a list of market-wide news items as styled cards."""
    if not news_items:
        st.markdown(
            '<p style="color: #484F58; font-size: 0.85rem;">No market news available right now.</p>',
            unsafe_allow_html=True,
        )
        return

    for item in news_items[:8]:
        title = item.get("title", "")
        url = item.get("url", "")
        publisher = item.get("publisher", "")
        published = item.get("published", "")[:10] if item.get("published") else ""
        summary = item.get("summary", "")

        st.markdown(
            f'<div class="news-item">'
            f'<a href="{url}" target="_blank">{title[:130]}</a>'
            + (f'<div style="color: #8B949E; font-size: 0.78rem; margin-top: 4px; line-height: 1.3;">{summary[:180]}</div>' if summary else "")
            + f'<div class="news-meta">{publisher}' + (f' · {published}' if published else "") + f'</div>'
            f'</div>',
            unsafe_allow_html=True,
        )


# ─── Watchlist Marquee (all pages) ──────────────────────────
render_watchlist_marquee()

# ─── Main Dashboard ────────────────────────────────────────
if page == "🏠 Dashboard":
    # Search bar
    ticker = st.text_input(
        "",
        placeholder="Enter a stock ticker (e.g., NVDA, AAPL, TSLA)...",
        key="ticker_search",
        label_visibility="collapsed",
    ).upper().strip()

    if not ticker:
        # ── Empty State: Market Overview Dashboard ──────────
        st.markdown(
            '<h1 style="color: #58A6FF; font-size: 2.2rem; margin-bottom: 4px;">📊 Sentinel</h1>'
            '<p style="color: #8B949E; font-size: 0.95rem; margin-bottom: 16px;">'
            'Fundamental analysis made simple. Type a stock ticker above to get an instant, plain-English analysis.</p>',
            unsafe_allow_html=True
        )

        # Market Indices Strip
        with st.spinner("Loading market data..."):
            indices_data = fetch_market_indices()
        if indices_data:
            render_indices_strip(indices_data)

        # Two-column layout: Top Movers + Market News
        col_left, col_right = st.columns([1, 1])

        with col_left:
            st.markdown('<div class="section-title">🔥 TODAY\'S TOP MOVERS</div>', unsafe_allow_html=True)
            with st.spinner("Scanning movers..."):
                movers = fetch_top_movers()
            render_top_movers(movers)

        with col_right:
            st.markdown('<div class="section-title">📰 LATEST MARKET NEWS</div>', unsafe_allow_html=True)
            with st.spinner("Fetching news..."):
                market_news = fetch_market_news()
            render_market_news_section(market_news)

        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown(
            '<div style="text-align: center; color: #484F58; font-size: 0.85rem; padding: 20px;">'
            '<p>Enter a ticker above for a full fundamental analysis:</p>'
            '<p>🟢 <strong>Health Score</strong> • 💰 <strong>Price Verdict</strong> • 🛡️ <strong>Risk Level</strong> • 📖 <strong>The Story</strong></p>'
            '<p style="margin-top: 16px;">Try: NVDA • AAPL • TSLA • MSFT • GOOGL • AMZN • META • JPM</p>'
            '</div>',
            unsafe_allow_html=True
        )
        st.stop()

    # Fetch data (with retry for transient Yahoo Finance issues)
    with st.spinner(f"Analyzing {ticker}..."):
        data = None
        for attempt in range(3):
            try:
                data = fetch_company_data(ticker)
                break  # success
            except Exception as e:
                import traceback
                print(f"[Sentinel] Attempt {attempt+1}/3 failed for {ticker}: {e}")
                traceback.print_exc()
                if attempt < 2:
                    import time
                    time.sleep(1.5 * (attempt + 1))  # 1.5s, 3s backoff
                else:
                    st.error(
                        f"Could not fetch data for {ticker} after 3 attempts. "
                        f"This is usually a temporary issue with the data provider. "
                        f"Please try again. ({e})"
                    )
                    st.stop()

    if data is None:
        st.error(f"Could not fetch data for {ticker}. Check the ticker symbol and try again.")
        st.stop()

    company = data.get("company", {})
    if not company.get("name"):
        st.error(f"No data found for ticker '{ticker}'. Please check the symbol and try again.")
        st.stop()

    # ── Kick off independent I/O fetches while we compute scores ──
    # All of these are independent of each other AND of the scoring
    # computations below.  Running them concurrently lets the I/O wait
    # overlap with the CPU-bound scoring work in the main thread.
    with ThreadPoolExecutor(max_workers=6) as _io_executor:
        _f_macro = _io_executor.submit(fetch_macro_context)
        _f_indices = _io_executor.submit(fetch_market_indices)
        _f_analyst = _io_executor.submit(fetch_analyst_data, ticker)
        _f_inst = _io_executor.submit(fetch_institutional_data, ticker)
        _f_movers = _io_executor.submit(fetch_top_movers)
        _f_news = _io_executor.submit(fetch_market_news)

        # Peers (depends on sector/industry from company data, but NOT on
        # the I/O fetches above — so do it in the main thread while I/O runs).
        peer_tickers = fetch_peers(company.get("sector", ""), company.get("industry", ""), ticker)
        peer_data = fetch_peer_metrics(peer_tickers) if peer_tickers else {}
        peer_averages = compute_peer_averages(peer_data) if peer_data else {}

        # Compute scores (CPU-bound — fast, runs while I/O is in flight)
        health_score, health_verdict, fscore, fscore_criteria = compute_health_score(data)
        z_score, z_zone, z_explanation = compute_altman_zscore(data)

        # Price verdict
        price_score, price_verdict, price_short, price_detail = compute_price_verdict(data, peer_averages)

        # Risk assessment
        risk_score, risk_label, risk_summary, risk_factors = compute_risk_assessment(data, z_score, z_zone)
        red_flags = compute_red_flags(data, risk_factors)

        # Intrinsic worth
        intrinsic_score, intrinsic_verdict, intrinsic_expl, intrinsic_detail, intrinsic_bd = compute_intrinsic_worth(data)
        # Build a short summary for the card
        if intrinsic_bd.get("graham_ratio"):
            intrinsic_summary = f"Trades at {intrinsic_bd['graham_ratio']}x Graham Number"
        elif intrinsic_bd.get("fcf_yield"):
            intrinsic_summary = f"FCF yield: {intrinsic_bd['fcf_yield']}%"
        else:
            intrinsic_summary = intrinsic_expl[:80]

        # ── Collect I/O results (most should be ready by now) ──
        macro_data = _f_macro.result()
        indices_data = _f_indices.result()
        analyst_data = _f_analyst.result()
        inst_data = _f_inst.result()
        movers = _f_movers.result()
        market_news = _f_news.result()

    # ─── Render Dashboard ──────────────────────────────

    # Company header
    desc = company.get('description', '')
    desc_text = desc[:500] + ('...' if len(desc) > 500 else '')
    emp_text = f" • {company.get('employees'):,} employees" if company.get('employees') else ""
    mcap_text = f" • {fmt_large_number(data.get('market', {}).get('market_cap'))} market cap" if data.get('market', {}).get('market_cap') else ""

    # 52-week range context
    mkt = data.get("market", {})
    price = mkt.get("price")
    hi_52w = mkt.get("52w_high")
    lo_52w = mkt.get("52w_low")
    range_pct = None
    if price and hi_52w and lo_52w and (hi_52w - lo_52w) > 0:
        range_pct = ((price - lo_52w) / (hi_52w - lo_52w)) * 100
    pct_off_high = None
    if price and hi_52w and hi_52w > 0:
        pct_off_high = ((price - hi_52w) / hi_52w) * 100

    range_html = ""
    if range_pct is not None and pct_off_high is not None:
        if pct_off_high > -2:
            range_color = "#00C853"  # near/at high
            range_label = "Near 52-week high"
        elif pct_off_high > -10:
            range_color = "#FFD600"
            range_label = f"{abs(pct_off_high):.0f}% below 52w high"
        elif pct_off_high > -25:
            range_color = "#FF9800"
            range_label = f"{abs(pct_off_high):.0f}% below 52w high"
        else:
            range_color = "#FF1744"
            range_label = f"{abs(pct_off_high):.0f}% below 52w high"

        range_html = (
            f'<span style="color: {range_color}; font-size: 0.85rem; font-weight: 600;">'
            f'📍 {range_label} — {range_pct:.0f}% of 52w range</span>'
        )

    st.markdown(
        f'<div class="company-header">'
        f"<h1>{company.get('name')} ({ticker})</h1>"
        f'<div class="meta">'
        f"{company.get('sector', '')} • {company.get('industry', '')}{emp_text}{mcap_text}"
        f'</div>'
        f'<div class="description">{desc_text}</div>'
        + (f'<div style="margin-top: 6px;">{range_html}</div>' if range_html else "") +
        f'</div>',
        unsafe_allow_html=True
    )

    st.markdown("<hr>", unsafe_allow_html=True)

    # Watchlist button
    wl_col1, wl_col2 = st.columns([1, 5])
    with wl_col1:
        if ticker not in st.session_state.watchlist:
            if st.button("⭐ Save to Watchlist", use_container_width=True, key=f"save_{ticker}"):
                st.session_state.watchlist.append(ticker)
                db_add_ticker(ticker)
                st.rerun()
        else:
            if st.button("✅ Saved", use_container_width=True, key=f"saved_{ticker}", help="Click to remove"):
                st.session_state.watchlist.remove(ticker)
                db_remove_ticker(ticker)
                st.rerun()

    # Live Price Ticker (updates every 5 seconds, client-side JS)
    initial_price = data.get("market", {}).get("price")
    prev_close = data.get("market", {}).get("previous_close")
    initial_change = ((initial_price - prev_close) / prev_close) if initial_price and prev_close else None
    render_live_ticker(ticker, initial_price, initial_change)

    # ── Market Macro Strip ───────────────────────────
    render_macro_strip(macro_data)

    # ── Market Indices Strip ─────────────────────────
    if indices_data:
        render_indices_strip(indices_data)

    # Headline Cards (4 cards)
    render_headline_cards(health_score, health_verdict,
                          price_score, price_verdict, price_short,
                          intrinsic_score, intrinsic_verdict, intrinsic_summary,
                          risk_score, risk_label, risk_summary)

    # ── Analyst Consensus ─────────────────────────────
    if analyst_data:
        st.markdown('<div class="section-title">🎯 ANALYST CONSENSUS</div>', unsafe_allow_html=True)
        render_analyst_consensus(analyst_data, company.get("name", ticker))

    st.markdown("<hr>", unsafe_allow_html=True)

    # Story
    story = render_story(data, health_verdict, price_verdict, intrinsic_verdict, risk_label, red_flags, macro_data)
    st.markdown(
        f'<div class="section-title">📖 THE STORY</div>'
        f'<div class="story-box">{story}</div>',
        unsafe_allow_html=True
    )

    # Key Numbers
    st.markdown('<div class="section-title">📊 KEY NUMBERS <span style="font-weight: 400; color: #8B949E; font-size: 0.8rem;">— what they mean in plain English</span></div>',
                unsafe_allow_html=True)
    render_key_numbers(data, peer_averages)

    # Quick help guide
    with st.expander("ℹ️ What do these numbers mean? — Quick Guide"):
        help_col1, help_col2 = st.columns(2)
        with help_col1:
            st.markdown("""
**P/E Ratio (TTM):** How many years of earnings it takes to equal the stock price. Lower = cheaper. Sector matters — tech stocks naturally have higher P/Es than banks.

**Forward P/E:** Same as P/E but using expected future earnings. If Forward P/E is much lower than TTM P/E, earnings are expected to grow a lot.

**PEG Ratio:** P/E divided by growth rate. Below 1.0 = potentially undervalued. Above 2.0 = expensive even with growth.

**P/B (Price-to-Book):** Stock price vs accounting value of assets. Below 1.0 = stock trades below asset value. Above 10 = market values intangibles (brand, tech) far above physical assets.

**EV/EBITDA:** Enterprise value vs operating profit. Better than P/E for comparing companies with different debt levels.

**ROE:** How much profit the company generates from shareholder money. Above 15% = good. Above 20% = excellent.
""")
        with help_col2:
            st.markdown("""
**Net Margin:** How much of each dollar of revenue becomes profit. Above 10% = good. Above 20% = excellent.

**ROIC:** Return on all invested capital (equity + debt). Above 10% = healthy. Above 15% = the company has a genuine competitive advantage.

**Revenue Growth:** How fast the top line is growing year-over-year. Above 15% = strong growth. Negative = business is shrinking.

**D/E (Debt-to-Equity):** How much debt vs shareholder equity. Below 50% = conservative. Above 200% = heavily leveraged — risky in a downturn.

**Beta:** How much the stock moves vs the market. 1.0 = moves with market. Above 1.5 = much more volatile.

**FCF (Free Cash Flow):** Real cash after all expenses and investments. Unlike earnings, this can't be manipulated. The company can use it to buy back shares, pay dividends, or invest in growth.

**Graham Number:** A conservative fair value estimate. If the stock trades above it, you're paying a premium for growth expectations.
""")

    st.markdown("<hr>", unsafe_allow_html=True)

    # News
    news_items = data.get("news", [])
    if news_items:
        st.markdown('<div class="section-title">📰 RECENT NEWS</div>', unsafe_allow_html=True)

        # ── Sentiment Meter ───────────────────────────
        sentiment = analyze_news_sentiment(news_items)
        render_sentiment_meter(sentiment)
        news_cols = st.columns(2)
        for i, item in enumerate(news_items[:6]):
            with news_cols[i % 2]:
                title = item.get("title", "")
                url = item.get("url", "")
                publisher = item.get("publisher", "")
                published = item.get("published", "")[:10] if item.get("published") else ""
                summary = item.get("summary", "")

                st.markdown(
                    f'<div class="key-card" style="margin-bottom: 10px;">'
                    f'<div style="font-size: 0.85rem; font-weight: 600; line-height: 1.3; margin-bottom: 4px;">'
                    f'<a href="{url}" target="_blank" style="color: #58A6FF; text-decoration: none;">{title[:120]}</a>'
                    f'</div>'
                    f'<div style="color: #8B949E; font-size: 0.7rem;">{publisher} · {published}</div>'
                    f'</div>',
                    unsafe_allow_html=True
                )
        st.markdown("<hr>", unsafe_allow_html=True)

    # Peer Comparison
    if peer_data:
        st.markdown('<div class="section-title">🏢 VS. SIMILAR COMPANIES</div>', unsafe_allow_html=True)
        render_peer_comparison(data, peer_data, peer_averages)

        st.markdown("<hr>", unsafe_allow_html=True)

    # ── Institutional Activity ─────────────────────────
    if inst_data and inst_data.get("holders"):
        st.markdown('<div class="section-title">🏛️ INSTITUTIONAL ACTIVITY</div>', unsafe_allow_html=True)
        render_institutional_activity(inst_data)
        st.markdown("<hr>", unsafe_allow_html=True)

    # ── Top Movers + Market News (pre-fetched concurrently) ─
    mover_col, news_col = st.columns([1, 1])

    with mover_col:
        st.markdown('<div class="section-title">🔥 TODAY\'S TOP MOVERS</div>', unsafe_allow_html=True)
        render_top_movers(movers)

    with news_col:
        st.markdown('<div class="section-title">📰 LATEST MARKET NEWS</div>', unsafe_allow_html=True)
        render_market_news_section(market_news)

    st.markdown("<hr>", unsafe_allow_html=True)

    # Trends (sparklines via Plotly)
    st.markdown('<div class="section-title">📈 TRENDS <span style="font-weight: 400; color: #8B949E; font-size: 0.8rem;">— 5-year view</span></div>',
                unsafe_allow_html=True)
    trends = data.get("trends", {})
    if any(trends.values()):
        import plotly.graph_objects as go

        trend_cols = st.columns(4)
        trend_data = [
            ("Revenue", trends.get("revenue", [])),
            ("Profit", trends.get("profit", [])),
            ("Debt", trends.get("debt", [])),
            ("Stock Price", trends.get("price", [])),
        ]

        for i, (label, values) in enumerate(trend_data):
            with trend_cols[i]:
                if values and len(values) > 1:
                    fig = go.Figure()
                    fig.add_trace(go.Scatter(
                        y=values,
                        mode="lines",
                        line=dict(color="#58A6FF", width=2),
                        fill="tozeroy",
                        fillcolor="rgba(88, 166, 255, 0.1)",
                        showlegend=False,
                    ))
                    fig.update_layout(
                        height=120,
                        margin=dict(l=0, r=0, t=20, b=20),
                        paper_bgcolor="rgba(0,0,0,0)",
                        plot_bgcolor="rgba(0,0,0,0)",
                        xaxis=dict(showticklabels=False, showgrid=False, zeroline=False),
                        yaxis=dict(showticklabels=False, showgrid=False, zeroline=False),
                    )
                    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
                    st.markdown(f"<div class='sparkline-label'>{label}</div>", unsafe_allow_html=True)
                else:
                    st.markdown(
                        f'<div style="text-align: center; color: #484F58; padding: 40px 0;">'
                        f'<p>{label}</p>'
                        f'<p style="font-size: 0.75rem;">No data</p>'
                        f'</div>',
                        unsafe_allow_html=True
                    )
    else:
        st.markdown('<p style="color: #484F58;">No trend data available.</p>', unsafe_allow_html=True)

    st.markdown("<hr>", unsafe_allow_html=True)

    # Red Flags
    st.markdown('<div class="section-title">⚠️ RED FLAGS & RISKS</div>', unsafe_allow_html=True)
    render_red_flags(red_flags)

    # ─── Deep Dive (Phase 4) ─────
    st.markdown("<br>", unsafe_allow_html=True)
    with st.expander("▶ SEE ALL DETAILS — Financial Statements, DCF Model, Full Analysis"):
        st.markdown("<br>", unsafe_allow_html=True)

        # F-Score Breakdown
        render_fscore_breakdown(fscore_criteria)

        st.markdown("<br>", unsafe_allow_html=True)

        # Z-Score Breakdown
        render_zscore_breakdown(data, z_score, z_zone)

        st.markdown("<br>", unsafe_allow_html=True)

        # Financial Statements
        render_financial_statements(data)

        st.markdown("<br>", unsafe_allow_html=True)

        # DCF Model
        render_dcf_model(data)


# ─── Watchlist Page ────────────────────────────────────────
elif page == "📋 Watchlist":
    st.markdown('<h2 style="color: #58A6FF;">📋 Watchlist</h2>', unsafe_allow_html=True)

    if not st.session_state.watchlist:
        st.markdown(
            '<div style="text-align: center; padding: 60px 20px;">'
            '<p style="color: #8B949E; font-size: 1.1rem;">Your watchlist is empty.</p>'
            '<p style="color: #484F58; font-size: 0.85rem;">Go to the Dashboard, analyze a stock, and click ⭐ Save to Watchlist.</p>'
            '</div>',
            unsafe_allow_html=True
        )
    else:
        st.markdown(f"Tracking **{len(st.session_state.watchlist)}** stock{'s' if len(st.session_state.watchlist) > 1 else ''}")
        st.markdown("<br>", unsafe_allow_html=True)

        for ticker in st.session_state.watchlist:
            # Fetch quick data
            try:
                from src.data.fetcher import fetch_company_data
                wl_data = fetch_company_data(ticker)
                wl_company = wl_data.get("company", {})
                wl_market = wl_data.get("market", {})
                wl_health = wl_data.get("health", {})

                # Quick health estimate
                from src.scoring.health import compute_health_score as _wl_health
                from src.scoring.common import score_to_color

                hs, hv, _, _ = _wl_health(wl_data)
                hc = score_to_color(hs)

                price = wl_market.get("price")
                pe = wl_data.get("valuation", {}).get("pe_ttm")
                name = wl_company.get("name", ticker)
                sector = wl_company.get("sector", "")

                # Build mini card
                st.markdown(
                    f'<div class="watchlist-card">'
                    f'<div style="display: flex; align-items: center; gap: 16px; flex: 1;">'
                    f'<div style="width: 12px; height: 12px; border-radius: 50%; background: {hc}; flex-shrink: 0;"></div>'
                    f'<div>'
                    f'<strong style="font-size: 1.05rem;">{name}</strong>'
                    f'<span style="color: #8B949E; margin-left: 8px; font-size: 0.85rem;">{ticker}</span>'
                    f'<div style="color: #8B949E; font-size: 0.75rem;">{sector}</div>'
                    f'</div>'
                    f'</div>'
                    f'<div style="text-align: right; flex-shrink: 0;">'
                    f'<div style="font-size: 1.2rem; font-weight: 700;">${price:.2f}</div>' if price else '<div>—</div>'
                    f'<div style="font-size: 0.8rem; color: {hc};">Health: {hv} ({hs}/100)</div>'
                    f'<div style="font-size: 0.75rem; color: #8B949E;">P/E: {pe:.0f}x</div>' if pe else '<div></div>'
                    f'</div>'
                    f'<div style="margin-left: 12px; flex-shrink: 0;">'
                    f'</div>'
                    f'</div>',
                    unsafe_allow_html=True
                )

                # Click to analyze
                if st.button(f"📊 Analyze", key=f"wl_analyze_{ticker}"):
                    st.session_state.analyze_ticker = ticker
                    st.session_state.page_override = "dashboard"

                # Remove button
                if st.button(f"🗑️", key=f"wl_remove_{ticker}", help=f"Remove {ticker} from watchlist"):
                    st.session_state.watchlist.remove(ticker)
                    db_remove_ticker(ticker)
                    st.rerun()

            except Exception as e:
                st.warning(f"Could not load data for {ticker}. It may have been delisted or the ticker is invalid.")
                if st.button(f"Remove {ticker}", key=f"wl_rm_bad_{ticker}"):
                    st.session_state.watchlist.remove(ticker)
                    db_remove_ticker(ticker)
                    st.rerun()

            st.markdown("<br>", unsafe_allow_html=True)

    # Clear all
    if st.session_state.watchlist:
        st.markdown("---")
        if st.button("🗑️ Clear Watchlist", key="wl_clear"):
            st.session_state.watchlist = []
            db_clear_watchlist()
            st.rerun()


# ─── Strategy Lab ──────────────────────────────────────────
elif page == "🎯 Strategy Lab":
    from src.display.strategy_sim import render_strategy_lab
    st.markdown('<h2 style="color: #58A6FF;">🎯 Strategy Lab</h2>', unsafe_allow_html=True)
    st.markdown(
        "Test and compare buy/sell strategies using historical price data. "
        "Enter a ticker, set your rules, and run thousands of simulated trades to see "
        "what outcomes you could expect."
    )

    lab_ticker = st.text_input(
        "",
        placeholder="Enter a ticker to simulate (e.g., NVDA, AAPL, MU)...",
        key="lab_ticker",
        label_visibility="collapsed",
    ).upper().strip()

    if lab_ticker:
        import yfinance as yf
        with st.spinner(f"Loading {lab_ticker} price data..."):
            t = yf.Ticker(lab_ticker)
            lab_data = fetch_company_data(lab_ticker)
            lab_price = t.history(period="5y")

        if lab_price.empty:
            st.error("No price data found for this ticker.")
        else:
            # Compute quick scores for the quality profile
            lab_health = 50
            lab_intrinsic = 50
            try:
                lab_health, _, _, _ = compute_health_score(lab_data)
                lab_intrinsic, _, _, _, _ = compute_intrinsic_worth(lab_data)
            except Exception:
                pass

            lab_data["health_score"] = lab_health
            lab_data["intrinsic_score"] = lab_intrinsic
            render_strategy_lab(lab_ticker, lab_price, lab_data)

# ─── Sector Search ──────────────────────────────────────────
elif page == "🔍 Sector Search":
    render_sector_search()

# ─── About Page ────────────────────────────────────────────
else:
    st.markdown(
        '<div style="max-width: 700px; margin: 40px auto;">'
        '<h2 style="color: #58A6FF;">ℹ️ About Sentinel</h2>'
        '<p>Sentinel is a fundamental analysis dashboard built for <strong>everyone</strong> — not just finance professionals.</p>'
        '<h3 style="color: #C9D1D9; margin-top: 30px;">Why We Built This</h3>'
        '<p>Most stock analysis tools are overwhelming. They throw 50 metrics at you, use jargon like '
        '"EV/EBITDA multiple expansion," and assume you have a finance degree. We think that\'s wrong.</p>'
        '<p>This dashboard answers the only three questions that matter:</p>'
        '<ul>'
        '<li><strong>Is this a good company?</strong> (Health Score)</li>'
        '<li><strong>Is the price fair?</strong> (Price Verdict)</li>'
        '<li><strong>What could go wrong?</strong> (Risk Level)</li>'
        '</ul>'
        '<h3 style="color: #C9D1D9; margin-top: 30px;">How It Works</h3>'
        '<p>We pull financial data from Yahoo Finance and run it through proven scoring systems:</p>'
        '<ul>'
        '<li><strong>Piotroski F-Score</strong> — 9-point check of financial strength (profitability, leverage, efficiency)</li>'
        '<li><strong>Altman Z-Score</strong> — Bankruptcy risk prediction (used by credit analysts since 1968)</li>'
        '<li><strong>Peer comparison</strong> — How this company stacks up against similar businesses</li>'
        '<li><strong>Red flag detection</strong> — Automated warnings for accounting, debt, and growth concerns</li>'
        '</ul>'
        '<p>Then we translate everything into <strong>plain English</strong>. Every number comes with an explanation '
        'anyone can understand.</p>'
        '<h3 style="color: #C9D1D9; margin-top: 30px;">Disclaimer</h3>'
        '<p style="color: #8B949E; font-size: 0.85rem;">'
        'This tool is for educational and informational purposes only. It does not constitute '
        'financial advice. Always do your own research before making investment decisions. '
        'Past performance does not guarantee future results.'
        '</p>'
        '</div>',
        unsafe_allow_html=True
    )
