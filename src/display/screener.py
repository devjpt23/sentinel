"""
Stock Screener display module.

Let users discover stocks by country and filter by basic criteria.
Uses OpenBB's yfinance-based screener — free, no API key required.
"""

import streamlit as st
import pandas as pd
from typing import Optional


# Country code → display name mapping
COUNTRY_OPTIONS = {
    "us": "🇺🇸 United States",
    "gb": "🇬🇧 United Kingdom",
    "ca": "🇨🇦 Canada",
    "au": "🇦🇺 Australia",
    "de": "🇩🇪 Germany",
    "fr": "🇫🇷 France",
    "jp": "🇯🇵 Japan",
    "cn": "🇨🇳 China",
    "in": "🇮🇳 India",
    "br": "🇧🇷 Brazil",
    "kr": "🇰🇷 South Korea",
    "hk": "🇭🇰 Hong Kong",
    "sg": "🇸🇬 Singapore",
    "ch": "🇨🇭 Switzerland",
    "nl": "🇳🇱 Netherlands",
    "se": "🇸🇪 Sweden",
    "it": "🇮🇹 Italy",
    "es": "🇪🇸 Spain",
    "all": "🌍 All Countries",
}


def render_screener_page():
    """Render the stock screener page."""
    st.markdown(
        '<h2 style="color: #58A6FF;">🔎 Stock Screener</h2>',
        unsafe_allow_html=True,
    )
    st.markdown(
        '<p style="color: #8B949E; margin-bottom: 16px;">'
        'Discover stocks by market. Data refreshes every 2 minutes. '
        'Click any ticker to analyze it in the dashboard.</p>',
        unsafe_allow_html=True,
    )

    # ── Controls ────────────────────────────────────────
    control_col1, control_col2, control_col3 = st.columns([1.5, 1, 1])

    with control_col1:
        country_choice = st.selectbox(
            "Market",
            options=list(COUNTRY_OPTIONS.keys()),
            format_func=lambda c: COUNTRY_OPTIONS.get(c, c),
            index=0,
            key="screener_country",
            label_visibility="collapsed",
        )

    with control_col2:
        sort_options = {
            "percent_change": "Biggest Movers",
            "market_cap": "Largest Cap",
            "price": "Highest Price",
            "volume": "Most Volume",
        }
        sort_by = st.selectbox(
            "Sort by",
            options=list(sort_options.keys()),
            format_func=lambda s: sort_options[s],
            index=0,
            key="screener_sort",
            label_visibility="collapsed",
        )

    with control_col3:
        max_results = st.selectbox(
            "Show",
            options=[25, 50, 100, 200],
            index=1,
            key="screener_limit",
            label_visibility="collapsed",
        )

    # ── Fetch ────────────────────────────────────────────
    from src.data.openbb_fetcher import fetch_screener_obb, OPENBB_AVAILABLE

    if not OPENBB_AVAILABLE:
        st.warning(
            "Screener data is currently unavailable. "
            "The OpenBB library is not installed in this environment."
        )
        return

    with st.spinner(f"Scanning {COUNTRY_OPTIONS.get(country_choice, country_choice)}..."):
        df = fetch_screener_obb(country=country_choice)

    if df is None or df.empty:
        st.warning("No screener data available right now. Please try again in a moment.")
        return

    # ── Apply filters ────────────────────────────────────
    # P/E filter
    pe_col1, pe_col2 = st.columns(2)
    with pe_col1:
        pe_min = st.number_input("P/E min", value=0.0, step=0.5, key="pe_min")
    with pe_col2:
        pe_max = st.number_input("P/E max", value=0.0, step=0.5, key="pe_max",
                                  help="0 = no limit")

    # Filter dataframe
    filtered = df.copy()

    # Apply P/E filters if set
    if "eps_ttm" in filtered.columns and "price" in filtered.columns:
        filtered["_pe"] = filtered.apply(
            lambda r: r["price"] / r["eps_ttm"]
            if r.get("eps_ttm") and r["eps_ttm"] > 0
            else None,
            axis=1,
        )
        if pe_min > 0:
            filtered = filtered[filtered["_pe"] >= pe_min]
        if pe_max > 0:
            filtered = filtered[filtered["_pe"] <= pe_max]

    # Market cap filter
    mcap_col1, mcap_col2 = st.columns(2)
    with mcap_col1:
        mcap_min = st.selectbox(
            "Min Market Cap",
            options=["Any", "Micro ($50M+)", "Small ($300M+)", "Mid ($2B+)",
                     "Large ($10B+)", "Mega ($200B+)"],
            index=0,
            key="mcap_min",
        )
    with mcap_col2:
        mcap_max = st.selectbox(
            "Max Market Cap",
            options=["Any", "Micro (<$300M)", "Small (<$2B)", "Mid (<$10B)",
                     "Large (<$200B)", "Mega (<$1T)"],
            index=0,
            key="mcap_max",
        )

    # Apply market cap filter
    mcap_thresholds_low = {
        "Micro ($50M+)": 50_000_000,
        "Small ($300M+)": 300_000_000,
        "Mid ($2B+)": 2_000_000_000,
        "Large ($10B+)": 10_000_000_000,
        "Mega ($200B+)": 200_000_000_000,
    }
    mcap_thresholds_high = {
        "Micro (<$300M)": 300_000_000,
        "Small (<$2B)": 2_000_000_000,
        "Mid (<$10B)": 10_000_000_000,
        "Large (<$200B)": 200_000_000_000,
        "Mega (<$1T)": 1_000_000_000_000,
    }

    if mcap_min != "Any" and "market_cap" in filtered.columns:
        threshold = mcap_thresholds_low[mcap_min]
        filtered = filtered[filtered["market_cap"] >= threshold]
    if mcap_max != "Any" and "market_cap" in filtered.columns:
        threshold = mcap_thresholds_high[mcap_max]
        filtered = filtered[filtered["market_cap"] <= threshold]

    # Sort
    if sort_by in filtered.columns:
        ascending = sort_by == "percent_change"
        filtered = filtered.sort_values(
            sort_by, ascending=not ascending, key=abs
        )

    # Limit
    filtered = filtered.head(max_results)

    # ── Render Results ──────────────────────────────────
    st.markdown(
        f'<p style="color: #8B949E; font-size: 0.8rem; margin-top: 12px;">'
        f'Showing {len(filtered)} of {len(df)} stocks</p>',
        unsafe_allow_html=True,
    )

    if filtered.empty:
        st.info("No stocks match your filters. Try widening the criteria.")
        return

    _render_screener_table(filtered)


def _render_screener_table(df: pd.DataFrame):
    """Render the screener results as a styled HTML table with clickable tickers."""
    rows_html = ""

    for _, row in df.iterrows():
        symbol = row.get("symbol", "")
        name = row.get("name", "")[:30]
        price = row.get("price")
        change_pct = row.get("percent_change")
        volume = row.get("volume")
        market_cap = row.get("market_cap")
        pe_val = row.get("_pe")

        # Format
        price_str = f"${price:,.2f}" if price and price == price else "—"
        change_str = (
            f"{change_pct:+.2f}%" if change_pct and change_pct == change_pct else "—"
        )
        change_color = (
            "#00C853" if (change_pct or 0) >= 0 else "#FF1744"
        )
        vol_str = f"{volume:,.0f}" if volume and volume == volume else "—"
        mcap_str = (
            f"${market_cap:,.0f}" if market_cap and market_cap == market_cap else "—"
        )
        pe_str = f"{pe_val:.1f}" if pe_val and pe_val == pe_val else "—"

        rows_html += (
            f'<tr style="border-bottom: 1px solid #21262D;">'
            f'<td style="padding: 10px 12px; white-space: nowrap;">'
            f'<strong style="font-size: 0.9rem;">{symbol}</strong>'
            f'</td>'
            f'<td style="padding: 10px 12px; color: #8B949E; max-width: 200px; '
            f'overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">'
            f'{name}</td>'
            f'<td style="padding: 10px 12px; text-align: right; '
            f'font-weight: 600;">{price_str}</td>'
            f'<td style="padding: 10px 12px; text-align: right; '
            f'color: {change_color}; font-weight: 600;">{change_str}</td>'
            f'<td style="padding: 10px 12px; text-align: right; '
            f'color: #8B949E;">{vol_str}</td>'
            f'<td style="padding: 10px 12px; text-align: right; '
            f'color: #8B949E;">{mcap_str}</td>'
            f'<td style="padding: 10px 12px; text-align: right; '
            f'color: #8B949E;">{pe_str}</td>'
            f'</tr>'
        )

    table_html = (
        f'<table style="width: 100%; border-collapse: collapse; font-size: 0.85rem;">'
        f'<thead>'
        f'<tr style="border-bottom: 1px solid #30363D;">'
        f'<th style="text-align: left; padding: 10px 12px; color: #8B949E; '
        f'font-weight: 600;">Ticker</th>'
        f'<th style="text-align: left; padding: 10px 12px; color: #8B949E; '
        f'font-weight: 600;">Company</th>'
        f'<th style="text-align: right; padding: 10px 12px; color: #8B949E; '
        f'font-weight: 600;">Price</th>'
        f'<th style="text-align: right; padding: 10px 12px; color: #8B949E; '
        f'font-weight: 600;">Change</th>'
        f'<th style="text-align: right; padding: 10px 12px; color: #8B949E; '
        f'font-weight: 600;">Volume</th>'
        f'<th style="text-align: right; padding: 10px 12px; color: #8B949E; '
        f'font-weight: 600;">Market Cap</th>'
        f'<th style="text-align: right; padding: 10px 12px; color: #8B949E; '
        f'font-weight: 600;">P/E</th>'
        f'</tr>'
        f'</thead>'
        f'<tbody>{rows_html}</tbody>'
        f'</table>'
    )

    st.markdown(table_html, unsafe_allow_html=True)

    # ── Click any ticker to analyze ──
    st.markdown("<br>", unsafe_allow_html=True)
    analyze_ticker = st.text_input(
        "Click a ticker in the table above to analyze it (or type one):",
        placeholder="e.g., AAPL",
        key="screener_analyze_ticker",
        label_visibility="collapsed",
    ).upper().strip()

    if analyze_ticker:
        st.session_state["_pending_ticker_search"] = analyze_ticker
        st.session_state["_nav_idx"] = 0  # switch to Dashboard
        st.rerun()
