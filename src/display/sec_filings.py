"""
SEC Filings + Insider Trading display module.

Shows recent SEC filings (10-K, 10-Q, 8-K) with links to SEC.gov,
and recent insider transactions (buys/sells) for a given ticker.

Uses OpenBB's SEC provider — free, no API key required.
"""

import streamlit as st
import pandas as pd
from typing import Optional


def render_sec_filings_page():
    """Render the SEC Filings & Insider Trading page."""
    st.markdown(
        '<h2 style="color: #58A6FF;">📄 SEC Filings & Insider Trading</h2>',
        unsafe_allow_html=True,
    )
    st.markdown(
        '<p style="color: #8B949E; margin-bottom: 16px;">'
        "View a company's recent SEC filings and insider trading activity. "
        "Data sourced directly from SEC EDGAR — no API key required.</p>",
        unsafe_allow_html=True,
    )

    ticker = st.text_input(
        "Enter a stock ticker",
        placeholder="Enter a stock ticker (e.g., AAPL, NVDA, TSLA)...",
        key="sec_ticker",
        label_visibility="collapsed",
    ).upper().strip()

    if not ticker:
        _render_empty_state()
        return

    # ── Fetch data ──────────────────────────────────────
    from src.data.openbb_fetcher import (
        fetch_sec_filings_obb,
        fetch_insider_trading_obb,
    )

    with st.spinner(f"Fetching SEC filings and insider trades for {ticker}..."):
        filings_df = fetch_sec_filings_obb(ticker)
        insider_df = fetch_insider_trading_obb(ticker)

    # ── Tabs ────────────────────────────────────────────
    tab1, tab2 = st.tabs(["📋 SEC Filings", "🔍 Insider Trading"])

    with tab1:
        _render_filings_tab(ticker, filings_df)

    with tab2:
        _render_insider_tab(ticker, insider_df)


# ═══════════════════════════════════════════════════════════════
#  Filings Tab
# ═══════════════════════════════════════════════════════════════


def _render_filings_tab(ticker: str, df: Optional[pd.DataFrame]):
    """Render the SEC filings table."""
    if df is None or df.empty:
        st.info(f"No SEC filings found for {ticker}.")
        return

    st.markdown(
        f"### {len(df)} most recent filings for {ticker}"
    )

    # Build a styled HTML table
    rows_html = ""
    for _, row in df.iterrows():
        report_type = row.get("report_type", "")
        filing_date = str(row.get("filing_date", ""))[:10]
        report_url = row.get("report_url", "")
        filing_detail_url = row.get("filing_detail_url", "")
        description = row.get("primary_doc_description", "")

        # Badge color by report type
        if report_type in ("10-K", "10-K/A", "20-F"):
            badge_color = "#00C853"
            badge_emoji = "📊"
        elif report_type in ("10-Q", "10-Q/A", "6-K"):
            badge_color = "#58A6FF"
            badge_emoji = "📋"
        elif report_type in ("8-K", "8-K/A"):
            badge_color = "#FFD600"
            badge_emoji = "⚡"
        elif "S-1" in str(report_type):
            badge_color = "#FF9800"
            badge_emoji = "🆕"
        else:
            badge_color = "#8B949E"
            badge_emoji = "📄"

        url = report_url or filing_detail_url or "#"
        rows_html += (
            f'<tr>'
            f'<td style="padding: 8px 12px; white-space: nowrap;">{filing_date}</td>'
            f'<td style="padding: 8px 12px;">'
            f'<span style="background: {badge_color}20; color: {badge_color}; '
            f'padding: 2px 8px; border-radius: 4px; font-weight: 600; '
            f'font-size: 0.8rem;">{badge_emoji} {report_type}</span>'
            f'</td>'
            f'<td style="padding: 8px 12px; color: #C9D1D9; '
            f'max-width: 400px; overflow: hidden; text-overflow: ellipsis; '
            f'white-space: nowrap;">{description}</td>'
            f'<td style="padding: 8px 12px;">'
            f'<a href="{url}" target="_blank" style="color: #58A6FF; '
            f'text-decoration: none; font-size: 0.8rem;">View →</a>'
            f'</td>'
            f'</tr>'
        )

    table_html = (
        f'<table style="width: 100%; border-collapse: collapse; font-size: 0.85rem;">'
        f'<thead>'
        f'<tr style="border-bottom: 1px solid #30363D;">'
        f'<th style="text-align: left; padding: 8px 12px; color: #8B949E; '
        f'font-weight: 600;">Date</th>'
        f'<th style="text-align: left; padding: 8px 12px; color: #8B949E; '
        f'font-weight: 600;">Type</th>'
        f'<th style="text-align: left; padding: 8px 12px; color: #8B949E; '
        f'font-weight: 600;">Description</th>'
        f'<th style="text-align: left; padding: 8px 12px; color: #8B949E; '
        f'font-weight: 600;">Link</th>'
        f'</tr>'
        f'</thead>'
        f'<tbody>{rows_html}</tbody>'
        f'</table>'
    )

    st.markdown(table_html, unsafe_allow_html=True)

    st.markdown(
        '<p style="color: #484F58; font-size: 0.7rem; margin-top: 12px;">'
        'Data sourced from SEC EDGAR via OpenBB. '
        '<a href="https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK='
        f'{ticker}" target="_blank" style="color: #58A6FF;">'
        'Search SEC.gov directly →</a></p>',
        unsafe_allow_html=True,
    )


# ═══════════════════════════════════════════════════════════════
#  Insider Trading Tab
# ═══════════════════════════════════════════════════════════════


def _render_insider_tab(ticker: str, df: Optional[pd.DataFrame]):
    """Render the insider trading table."""
    if df is None or df.empty:
        st.info(
            f"No insider trading data found for {ticker}. "
            "This could mean no recent insider transactions, "
            "or the SEC data feed is temporarily unavailable."
        )
        return

    # Filter and clean
    display_cols = [
        "transaction_date", "owner_name", "owner_title",
        "transaction_type", "securities_transacted",
        "transaction_price", "filing_url",
    ]
    available = [c for c in display_cols if c in df.columns]
    display_df = df[available].copy()

    st.markdown(f"### {len(display_df)} recent insider transactions for {ticker}")

    # Build HTML table
    rows_html = ""
    for _, row in display_df.iterrows():
        txn_date = str(row.get("transaction_date", ""))[:10]
        owner = str(row.get("owner_name", ""))[:30]
        title = str(row.get("owner_title", ""))[:25]
        txn_type = str(row.get("transaction_type", ""))
        shares = row.get("securities_transacted")
        price = row.get("transaction_price")
        filing_url = row.get("filing_url", "#")

        # Color-code: buy = green, sell = red
        is_buy = "purchase" in txn_type.lower() or "buy" in txn_type.lower() or "award" in txn_type.lower()
        is_sell = "sale" in txn_type.lower() or "sell" in txn_type.lower()

        if is_buy:
            txn_color = "#00C853"
            txn_emoji = "🟢"
        elif is_sell:
            txn_color = "#FF1744"
            txn_emoji = "🔴"
        else:
            txn_color = "#8B949E"
            txn_emoji = "⚪"

        shares_str = f"{shares:,.0f}" if shares and shares == shares else "—"
        price_str = f"${price:,.2f}" if price and price == price else "—"

        rows_html += (
            f'<tr>'
            f'<td style="padding: 8px 10px; white-space: nowrap;">{txn_date}</td>'
            f'<td style="padding: 8px 10px; font-weight: 600;">{owner}</td>'
            f'<td style="padding: 8px 10px; color: #8B949E; font-size: 0.8rem;">{title}</td>'
            f'<td style="padding: 8px 10px; color: {txn_color}; font-weight: 600;">'
            f'{txn_emoji} {txn_type}</td>'
            f'<td style="padding: 8px 10px; text-align: right;">{shares_str}</td>'
            f'<td style="padding: 8px 10px; text-align: right;">{price_str}</td>'
            f'<td style="padding: 8px 10px;">'
            f'<a href="{filing_url}" target="_blank" style="color: #58A6FF; '
            f'text-decoration: none; font-size: 0.8rem;">Filing →</a>'
            f'</td>'
            f'</tr>'
        )

    table_html = (
        f'<table style="width: 100%; border-collapse: collapse; font-size: 0.85rem;">'
        f'<thead>'
        f'<tr style="border-bottom: 1px solid #30363D;">'
        f'<th style="text-align: left; padding: 8px 10px; color: #8B949E;">Date</th>'
        f'<th style="text-align: left; padding: 8px 10px; color: #8B949E;">Insider</th>'
        f'<th style="text-align: left; padding: 8px 10px; color: #8B949E;">Role</th>'
        f'<th style="text-align: left; padding: 8px 10px; color: #8B949E;">Type</th>'
        f'<th style="text-align: right; padding: 8px 10px; color: #8B949E;">Shares</th>'
        f'<th style="text-align: right; padding: 8px 10px; color: #8B949E;">Price</th>'
        f'<th style="text-align: left; padding: 8px 10px; color: #8B949E;"></th>'
        f'</tr>'
        f'</thead>'
        f'<tbody>{rows_html}</tbody>'
        f'</table>'
    )

    st.markdown(table_html, unsafe_allow_html=True)

    # Summary stats
    if len(display_df) > 0:
        buy_count = sum(
            1 for _, r in display_df.iterrows()
            if "purchase" in str(r.get("transaction_type", "")).lower()
            or "buy" in str(r.get("transaction_type", "")).lower()
        )
        sell_count = sum(
            1 for _, r in display_df.iterrows()
            if "sale" in str(r.get("transaction_type", "")).lower()
            or "sell" in str(r.get("transaction_type", "")).lower()
        )
        st.markdown(
            f'<div style="margin-top: 12px; font-size: 0.85rem; color: #8B949E;">'
            f'<span style="color: #00C853;">🟢 {buy_count} buys</span> &nbsp;&nbsp;'
            f'<span style="color: #FF1744;">🔴 {sell_count} sells</span> &nbsp;&nbsp;'
            f'<span>⚪ {len(display_df) - buy_count - sell_count} other</span>'
            f'</div>',
            unsafe_allow_html=True,
        )

    st.markdown(
        '<p style="color: #484F58; font-size: 0.7rem; margin-top: 12px;">'
        'Data sourced from SEC EDGAR via OpenBB. Insider transactions are '
        'reported on Forms 3, 4, and 5.</p>',
        unsafe_allow_html=True,
    )


# ═══════════════════════════════════════════════════════════════
#  Empty State
# ═══════════════════════════════════════════════════════════════


def _render_empty_state():
    """Render the initial empty state with example tickers."""
    st.markdown(
        '<div style="text-align: center; padding: 60px 20px;">'
        '<p style="color: #C9D1D9; font-size: 1.1rem;">'
        '📄 Enter a ticker above to view SEC filings and insider trading activity.</p>'
        '<p style="color: #8B949E; font-size: 0.85rem;">'
        'See when companies file their 10-K, 10-Q, and 8-K reports, '
        'and track what insiders are buying and selling.</p>'
        '<p style="color: #484F58; font-size: 0.8rem; margin-top: 16px;">'
        'Try: AAPL · NVDA · TSLA · MSFT · AMZN · META</p>'
        '</div>',
        unsafe_allow_html=True,
    )
