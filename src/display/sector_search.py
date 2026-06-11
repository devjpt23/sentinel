"""
Sector Search page — search by sector or industry, view all companies,
compare key metrics in a sortable table, and discover company relationships.

This is a full-page renderer that becomes the " Sector Search" nav option.
"""

import streamlit as st
import pandas as pd

from src.data.sector_universe import (
    get_all_sectors,
    search_sectors,
    search_industries,
    get_companies_in_sector,
    get_companies_in_industry,
    get_industries_for_sector,
)
from src.data.fetcher import fetch_batch_metrics
from src.display.company_linkage import render_sector_linkage
from src.utils.formatters import fmt_large_number


def render_sector_search():
    """Main entry point: renders the full Sector Search page."""
    st.markdown(
        '<h2 style="color: #58A6FF; margin-bottom: 4px;">\U0001f50d Sector Search</h2>',
        unsafe_allow_html=True,
    )
    st.markdown(
        '<p style="color: #8B949E; font-size: 0.9rem; margin-bottom: 20px;">'
        "Explore entire sectors — compare companies side-by-side and discover "
        "how they're connected.</p>",
        unsafe_allow_html=True,
    )

    # --- State initialization ---
    if "sector_cache" not in st.session_state:
        st.session_state.sector_cache = {}

    # --- Search bar ---
    query = _render_search_bar()

    if not query:
        _render_empty_state()
        return

    # --- Resolve search: sector? industry? ---
    matched_sectors = search_sectors(query)
    matched_industries = search_industries(query)

    if not matched_sectors and not matched_industries:
        st.info(
            f'No sectors or industries matching **"{query}"**. '
            f"Try: Technology, Semiconductors, Healthcare, Financials, Energy..."
        )
        _render_popular_tags()
        return

    # --- Sector / Industry picker ---
    col_sector, col_industry = st.columns(2)
    with col_sector:
        # If user searched something that matched an industry, auto-select the parent sector
        if matched_sectors:
            default_sector_idx = 0
            selected_sector = st.selectbox(
                "Sector",
                matched_sectors,
                index=default_sector_idx,
                key="sector_picker",
            )
        else:
            # Industry matched but no sector? Show all sectors
            all_sectors = get_all_sectors()
            selected_sector = st.selectbox(
                "Sector",
                all_sectors,
                key="sector_picker_all",
            )

    with col_industry:
        industries_in_sector = get_industries_for_sector(selected_sector)
        industry_options = ["All Industries"] + industries_in_sector

        # Auto-select the matching industry if the user searched for one
        if matched_industries:
            # Find which matched industry is in this sector
            auto_industry = None
            for mi in matched_industries:
                if mi in industries_in_sector:
                    auto_industry = mi
                    break
            default_idx = industry_options.index(auto_industry) if auto_industry else 0
        else:
            default_idx = 0

        selected_industry = st.selectbox(
            "Industry",
            industry_options,
            index=default_idx,
            key="industry_picker",
        )

    # --- Get companies ---
    if selected_industry != "All Industries":
        companies = get_companies_in_industry(selected_industry)
    else:
        companies = get_companies_in_sector(selected_sector)

    if not companies:
        st.warning(f"No companies found in {selected_sector} / {selected_industry}.")
        return

    # Show count
    industry_label = f" · {selected_industry}" if selected_industry != "All Industries" else ""
    st.markdown(
        f'<div style="color: #8B949E; font-size: 0.9rem; margin: 12px 0 16px 0;">'
        f"<strong>{selected_sector}</strong>{industry_label} "
        f"· {len(companies)} companies</div>",
        unsafe_allow_html=True,
    )

    # --- Fetch & Render ---
    _render_results(companies, selected_sector, selected_industry)


def _render_search_bar() -> str:
    """Render the sector search input and return the current query string."""
    query = st.text_input(
        "",
        placeholder="Search for a sector or industry (e.g., Technology, Semiconductors, Healthcare)...",
        key="sector_search_input",
        label_visibility="collapsed",
    ).strip()
    return query


def _render_empty_state():
    """Show popular sectors as quick-access chips when no search has been done."""
    st.markdown(
        '<div style="text-align: center; padding: 50px 20px 30px 20px;">'
        '<p style="color: #8B949E; font-size: 1.05rem;">'
        "Search for a sector or industry above to get started.</p>"
        '<p style="color: #484F58; font-size: 0.85rem;">'
        "Or try one of these popular sectors:</p>"
        "</div>",
        unsafe_allow_html=True,
    )
    _render_popular_tags()


def _render_popular_tags():
    """Render clickable sector tag buttons for quick access."""
    popular = [
        "Information Technology",
        "Health Care",
        "Financials",
        "Consumer Discretionary",
        "Industrials",
        "Energy",
        "Communication Services",
    ]
    # Use a wrapping grid of columns (4 per row)
    rows = [popular[i:i + 4] for i in range(0, len(popular), 4)]
    for row in rows:
        cols = st.columns(len(row))
        for i, sector in enumerate(row):
            with cols[i]:
                if st.button(sector, key=f"tag_{sector}", use_container_width=True):
                    st.session_state.sector_search_input = sector
                    st.rerun()


def _render_results(companies: list[dict], sector: str, industry: str):
    """Fetch batch metrics and render the company table + relationship section."""
    tickers = [c["ticker"] for c in companies]
    cache_key = f"{sector}|{industry}".lower()

    # --- Fetch (with session cache) ---
    if cache_key in st.session_state.sector_cache:
        metrics_data = st.session_state.sector_cache[cache_key]
    else:
        with st.status(
            f"Loading live data for {len(tickers)} companies..."
        ) as status:
            metrics_data = fetch_batch_metrics(tickers)
            if metrics_data:
                st.session_state.sector_cache[cache_key] = metrics_data
                status.update(
                    label=f"Loaded {len(metrics_data)} of {len(tickers)} companies",
                    state="complete",
                )
            else:
                status.update(
                    label="Could not load data — the API may be rate-limited",
                    state="error",
                )

    if not metrics_data:
        st.warning(
            "Could not fetch live data for this sector. "
            "The Yahoo Finance API may be rate-limited. "
            "Wait a moment and try again."
        )
        return

    # --- Show All toggle ---
    show_all = st.checkbox(
        "Show all companies",
        value=False,
        key="show_all_toggle",
        help="By default, only the top 30 by market cap are shown.",
    )

    # --- Build table data ---
    rows = []
    for ticker, data in metrics_data.items():
        if data is None:
            continue
        qh = data.get("quick_health", {}) or {}
        rows.append({
            "Ticker": ticker,
            "Company": data.get("name", ticker),
            "Market Cap": data.get("market_cap") or 0,
            "Price": data.get("price"),
            "P/E": data.get("pe_ttm"),
            "Rev Growth": data.get("revenue_growth"),
            "Health": qh.get("verdict", "N/A"),
            "_health_score": qh.get("score", 0),
        })

    if not rows:
        st.info("No live data available for any company in this group.")
        return

    df = pd.DataFrame(rows)
    df = df.sort_values("Market Cap", ascending=False)

    # Limit to top 30 unless user wants all
    display_df = df.head(30) if not show_all else df
    if not show_all and len(df) > 30:
        st.caption(
            f"Showing top 30 of {len(df)} companies by market cap. "
            f"Check “Show all companies” to see the rest."
        )

    # Format for display
    display_df["Market Cap"] = display_df["Market Cap"].apply(
        lambda x: fmt_large_number(x) if x and x > 0 else "N/A"
    )
    display_df["Price"] = display_df["Price"].apply(
        lambda x: f"${x:.2f}" if x is not None and x > 0 else "N/A"
    )
    display_df["P/E"] = display_df["P/E"].apply(
        lambda x: f"{x:.1f}x" if x is not None and x > 0 else "N/A"
    )
    display_df["Rev Growth"] = display_df["Rev Growth"].apply(
        lambda x: f"{x*100:+.1f}%" if x is not None else "N/A"
    )

    # Remove internal score before display
    display_df = display_df.drop(columns=["_health_score"])

    # Column config for cleaner display
    column_config = {
        "Ticker": st.column_config.TextColumn("Ticker", width="small"),
        "Company": st.column_config.TextColumn("Company", width="medium"),
        "Market Cap": st.column_config.TextColumn("Market Cap", width="small"),
        "Price": st.column_config.TextColumn("Price", width="small"),
        "P/E": st.column_config.TextColumn("P/E", width="small"),
        "Rev Growth": st.column_config.TextColumn("Rev Growth", width="small"),
        "Health": st.column_config.TextColumn("Health", width="small"),
    }

    st.dataframe(
        display_df,
        column_config=column_config,
        use_container_width=True,
        hide_index=True,
    )

    # --- Quick Analyze buttons ---
    top_n = min(12, len(display_df))
    st.markdown(
        '<p style="color: #8B949E; font-size: 0.85rem; margin: 16px 0 8px 0;">'
        "<strong>Quick Analyze</strong> — click any ticker to open its full "
        "Dashboard analysis:</p>",
        unsafe_allow_html=True,
    )
    # Render buttons in rows of 6
    btn_rows = [list(range(i, min(i + 6, top_n))) for i in range(0, top_n, 6)]
    for row_indices in btn_rows:
        cols = st.columns(len(row_indices))
        for col_i, idx in enumerate(row_indices):
            row = display_df.iloc[idx]
            ticker = row["Ticker"]
            with cols[col_i]:
                if st.button(ticker, key=f"qa_{ticker}", use_container_width=True):
                    st.session_state["ticker_search"] = ticker
                    st.session_state["_nav_idx"] = 0  # Dashboard
                    st.rerun()

    st.markdown("<hr>", unsafe_allow_html=True)

    # --- Company Linkage Section ---
    st.markdown(
        '<div class="section-title">\U0001f517 COMPANY RELATIONSHIPS</div>',
        unsafe_allow_html=True,
    )
    render_sector_linkage(tickers, metrics_data)
