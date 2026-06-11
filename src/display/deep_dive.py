"""
Deep Dive display components for Phase 4.
Financial statements, DCF model, F-Score breakdown, Z-Score breakdown.
All rendered within the expandable "See All Details" section.
"""

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from typing import Dict, Any, List, Tuple, Optional

from src.scoring.dcf import compute_dcf
from src.utils.formatters import fmt_large_number, fmt_pct


def render_financial_statements(data: Dict[str, Any]):
    """Render income statement, balance sheet, and cash flow in clean tables."""
    statements = data.get("statements", {})

    st.markdown("### 📋 Financial Statements")
    st.markdown("*Last 5 fiscal years. Click column headers to sort.*")

    tabs = st.tabs(["Income Statement", "Balance Sheet", "Cash Flow"])

    with tabs[0]:
        income = statements.get("income")
        if income is not None and not income.empty:
            _render_statement_table(income, "Income Statement")
        else:
            st.info("Income statement data not available.")

    with tabs[1]:
        balance = statements.get("balance")
        if balance is not None and not balance.empty:
            _render_statement_table(balance, "Balance Sheet")
        else:
            st.info("Balance sheet data not available.")

    with tabs[2]:
        cashflow = statements.get("cashflow")
        if cashflow is not None and not cashflow.empty:
            _render_statement_table(cashflow, "Cash Flow Statement")
        else:
            st.info("Cash flow data not available.")


def _render_statement_table(df: pd.DataFrame, title: str):
    """Render a single financial statement as a styled dataframe."""
    if df.empty:
        st.info(f"{title} data not available.")
        return

    # Transpose for better display (years as rows, items as columns would be too wide)
    # Instead, show years as columns and key items as rows
    display_df = df.copy()

    # Format: round to millions/billions and add commas
    def fmt_financial(val):
        if pd.isna(val) or val == 0:
            return "—"
        if abs(val) >= 1e9:
            return f"${val/1e9:,.1f}B"
        if abs(val) >= 1e6:
            return f"${val/1e6:,.0f}M"
        return f"${val:,.0f}"

    # Rename columns to show just the year
    display_df.columns = [str(c).split("-")[0] if hasattr(c, 'split') else str(c)[:4]
                          for c in display_df.columns]

    styled = display_df.map(fmt_financial)
    st.dataframe(styled, use_container_width=True, height=400)


def render_fscore_breakdown(fscore_criteria: List[Tuple[str, bool, str]]):
    """Render the 9-point Piotroski F-Score checklist."""
    if not fscore_criteria:
        st.info("F-Score breakdown not available.")
        return

    passed_count = sum(1 for _, passed, _ in fscore_criteria if passed)
    total = len(fscore_criteria)

    st.markdown(f"### 🔍 Piotroski F-Score: {passed_count}/{total}")
    st.markdown("*Measures financial strength across profitability, leverage, and efficiency. Higher = stronger.*")

    categories = {
        "Profitability": fscore_criteria[:4],
        "Leverage & Liquidity": fscore_criteria[4:7],
        "Operating Efficiency": fscore_criteria[7:],
    }

    for cat_name, criteria in categories.items():
        st.markdown(f"**{cat_name}**")
        for name, passed, explanation in criteria:
            icon = "✅" if passed else "❌"
            color = "#00C853" if passed else "#FF1744"
            st.markdown(
                f'<div style="padding: 6px 0; font-size: 0.9rem;">'
                f'<span style="color: {color}; font-weight: 700;">{icon}</span> '
                f'<strong>{name}</strong><br>'
                f'<span style="color: #8B949E; font-size: 0.8rem; margin-left: 28px;">{explanation}</span>'
                f'</div>',
                unsafe_allow_html=True
            )
        st.markdown("<br>", unsafe_allow_html=True)


def render_zscore_breakdown(data: Dict[str, Any], z_score: Optional[float], z_zone: str):
    """Render the Altman Z-Score component breakdown."""
    if z_score is None:
        st.info("Z-Score not available — requires balance sheet data.")
        return

    statements = data.get("statements", {})
    balance = statements.get("balance")
    income = statements.get("income")
    market = data.get("market", {})

    st.markdown(f"### 🏦 Altman Z-Score: {z_score:.2f} ({z_zone})")
    st.markdown("*Predicts bankruptcy risk within 2 years. Above 2.6 = safe, 1.1-2.6 = grey zone, below 1.1 = distress.*")

    # Extract components
    try:
        wc = _get_value(balance, "Working Capital") or (
            _get_value(balance, "Current Assets") - _get_value(balance, "Current Liabilities")
            if _get_value(balance, "Current Assets") and _get_value(balance, "Current Liabilities")
            else 0
        )
        ta = _get_value(balance, "Total Assets") or 1
        re_val = _get_value(balance, "Retained Earnings") or 0
        ebit = _get_value(income, "EBIT") or _get_value(income, "Operating Income") or 0
        mv_equity = market.get("market_cap") or 0
        tl = _get_value(balance, "Total Liabilities") or 1

        x1 = wc / ta if ta else 0
        x2 = re_val / ta if ta else 0
        x3 = ebit / ta if ta else 0
        x4 = mv_equity / tl if tl else 0

        components = [
            ("X₁ = Working Capital / Assets", x1, 6.56, "Measures short-term liquidity buffer"),
            ("X₂ = Retained Earnings / Assets", x2, 3.26, "Measures cumulative profitability and age"),
            ("X₃ = EBIT / Assets", x3, 6.72, "Measures operating efficiency — the most important factor"),
            ("X₄ = Market Cap / Liabilities", x4, 1.05, "Measures how much market value cushions creditors"),
        ]

        # Build a clean table-like display
        for label, value, weight, desc in components:
            contribution = value * weight
            color = "#00C853" if value > 0 else "#FF1744"
            st.markdown(
                f'<div style="padding: 8px 0; border-bottom: 1px solid #21262D;">'
                f'<div style="display: flex; justify-content: space-between;">'
                f'<span style="font-weight: 600;">{label}</span>'
                f'<span style="color: {color};">Value: {value:.3f} × Weight: {weight:.1f} = <strong>{contribution:.3f}</strong></span>'
                f'</div>'
                f'<div style="color: #8B949E; font-size: 0.75rem; margin-top: 2px;">{desc}</div>'
                f'</div>',
                unsafe_allow_html=True
            )

        st.markdown(
            f'<div style="padding: 12px 0; margin-top: 8px; font-weight: 700; font-size: 1.1rem;">'
            f'Total Z-Score = {6.56*x1 + 3.26*x2 + 6.72*x3 + 1.05*x4:.2f} → <span style="color: #58A6FF;">{z_zone} Zone</span>'
            f'</div>',
            unsafe_allow_html=True
        )

    except Exception as e:
        st.warning(f"Could not compute Z-Score components: {e}")


def _get_value(df, keyword: str) -> float:
    """Get latest value from a financial dataframe by keyword match."""
    if df is None or df.empty:
        return 0
    for label in df.index:
        if keyword.lower() in str(label).lower():
            vals = df.loc[label].dropna()
            if not vals.empty:
                return float(vals.iloc[0])
    return 0


def render_dcf_model(data: Dict[str, Any]):
    """Render interactive DCF model with sliders and sensitivity analysis."""
    st.markdown("### 💰 Discounted Cash Flow (DCF) Model")
    st.markdown("*Project what the company is worth based on its future cash generation. Adjust the sliders to test different scenarios.*")

    health = data.get("health", {})
    market = data.get("market", {})
    growth_data = data.get("growth", {})

    current_price = market.get("price")
    rev_growth = growth_data.get("revenue_growth_yoy")

    # Smart defaults based on company data
    default_growth = 0.10  # default 10%
    if rev_growth is not None:
        # Use recent growth but cap at 15% — anything above is unsustainable
        default_growth = min(rev_growth, 0.15)
        default_growth = max(default_growth, 0.03)  # minimum 3%

    col1, col2 = st.columns(2)

    with col1:
        rev_growth_input = st.slider(
            "Revenue Growth (next 5 years)",
            min_value=0.0,
            max_value=0.50,
            value=float(default_growth),
            step=0.01,
            format="%.0f%%",
            key="rev_growth_slider",
            help="How fast do you expect revenue to grow each year for the next 5 years?",
        )

        terminal_growth = st.slider(
            "Terminal Growth Rate (after 5 years)",
            min_value=0.01,
            max_value=0.05,
            value=0.03,
            step=0.005,
            format="%.1f%%",
            key="terminal_growth_slider",
            help="Long-term growth rate. Usually 2-3% (roughly inflation + population growth).",
        )

    with col2:
        discount_rate = st.slider(
            "Discount Rate (your required return)",
            min_value=0.06,
            max_value=0.20,
            value=0.10,
            step=0.005,
            format="%.1f%%",
            key="discount_rate_slider",
            help="The annual return you require. Higher = more conservative. 10% is a common starting point.",
        )

        margin_improvement = st.slider(
            "Margin Improvement (per year)",
            min_value=-0.02,
            max_value=0.05,
            value=0.0,
            step=0.005,
            format="%.1f%%",
            key="margin_slider",
            help="How much profit margins improve each year. 0% = margins stay flat.",
        )

    # Run DCF
    dcf_result = compute_dcf(
        data,
        revenue_growth_5yr=rev_growth_input,
        terminal_growth=terminal_growth,
        discount_rate=discount_rate,
        margin_improvement=margin_improvement,
    )

    if dcf_result.get("error"):
        st.warning(dcf_result["error"])
        return

    # ─── Results Display ───
    st.markdown("<br>", unsafe_allow_html=True)

    res_col1, res_col2, res_col3 = st.columns(3)

    fair_value = dcf_result["fair_value_with_cash"]
    upside = dcf_result["upside_pct"]
    verdict = dcf_result["verdict"]

    upside_color = "#00C853" if upside and upside > 0 else "#FF1744" if upside else "#8B949E"
    upside_emoji = "🟢" if upside and upside > 0 else "🔴" if upside else "⚪"

    with res_col1:
        st.markdown(
            f'<div class="metric-card">'
            f'<h3>Fair Value</h3>'
            f'<div class="score" style="color: #58A6FF;">${fair_value:.2f}</div>'
            f'<div class="verdict">per share</div>'
            f'<div class="detail">Current price: ${current_price:.2f}</div>'
            f'</div>',
            unsafe_allow_html=True
        )

    with res_col2:
        st.markdown(
            f'<div class="metric-card">'
            f'<h3>{upside_emoji} Upside / Downside</h3>'
            f'<div class="score" style="color: {upside_color};">{upside:+.1f}%</div>'
            f'<div class="verdict">{verdict}</div>'
            f'<div class="detail">{"Below" if upside and upside < 0 else "Above"} current price</div>'
            f'</div>',
            unsafe_allow_html=True
        )

    with res_col3:
        ev = dcf_result["enterprise_value"]
        st.markdown(
            f'<div class="metric-card">'
            f'<h3>Enterprise Value</h3>'
            f'<div class="score" style="color: #C9D1D9; font-size: 1.8rem;">{fmt_large_number(ev)}</div>'
            f'<div class="verdict">Total business value</div>'
            f'<div class="detail">{fmt_large_number(dcf_result["shares_outstanding"])} shares</div>'
            f'</div>',
            unsafe_allow_html=True
        )

    # ─── Projection Table ───
    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown("**Projected Free Cash Flows**")

    proj_data = {
        "Year": ["Year 1", "Year 2", "Year 3", "Year 4", "Year 5", "Terminal"],
        "Revenue": dcf_result["projected_revenue"] + [None],
        "FCF": dcf_result["projected_fcf"] + [None],
        "Present Value": dcf_result["pv_fcf"] + [dcf_result["pv_terminal"]],
    }

    proj_df = pd.DataFrame(proj_data)
    proj_df["Revenue"] = proj_df["Revenue"].apply(
        lambda x: fmt_large_number(x) if x else "—"
    )
    proj_df["FCF"] = proj_df["FCF"].apply(
        lambda x: fmt_large_number(x) if x else "—"
    )
    proj_df["Present Value"] = proj_df["Present Value"].apply(
        lambda x: fmt_large_number(x) if x and x > 0 else "—"
    )
    proj_df.at[5, "Revenue"] = "—"
    proj_df.at[5, "FCF"] = f"{fmt_large_number(dcf_result['terminal_value'])} (TV)"

    st.dataframe(proj_df, use_container_width=True, hide_index=True)

    # ─── Sensitivity Heatmap ───
    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown("**Sensitivity: Upside % at Different Assumptions**")
    st.markdown("*Shows how fair value changes if growth or discount rate differ from your inputs.*")

    sens = dcf_result["sensitivity"]
    matrix = sens["matrix"]
    wacc_labels = [f"{w}%" for w in sens["wacc_range"]]
    growth_labels = [f"{g}%" for g in sens["growth_range"]]

    # Create heatmap
    fig = go.Figure(data=go.Heatmap(
        z=matrix,
        x=wacc_labels,
        y=growth_labels,
        colorscale=[
            [0.0, "#FF1744"],    # very overvalued
            [0.35, "#FF6B7A"],    # overvalued
            [0.45, "#FFD600"],    # grey/neutral
            [0.55, "#A5D6A7"],    # slightly undervalued
            [0.7, "#00C853"],    # undervalued
            [1.0, "#00E676"],    # very undervalued
        ],
        zmin=-30,
        zmax=30,
        text=[[f"{v:+.1f}%" if v is not None else "N/A" for v in row] for row in matrix],
        texttemplate="%{text}",
        textfont={"size": 11, "color": "#C9D1D9"},
        showscale=True,
        colorbar=dict(
            title=dict(text="Upside %", side="right"),
            tickfont=dict(color="#8B949E"),
        ),
    ))

    fig.update_layout(
        title="",
        xaxis_title="Discount Rate (WACC) →",
        yaxis_title="Revenue Growth Rate →",
        height=280,
        margin=dict(l=10, r=10, t=10, b=10),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        xaxis=dict(showgrid=False, color="#8B949E"),
        yaxis=dict(showgrid=False, color="#8B949E"),
    )

    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})

    # ─── Key Assumptions Summary ───
    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown("**Your Assumptions**")
    ass = dcf_result["assumptions"]
    a_col1, a_col2, a_col3, a_col4 = st.columns(4)
    with a_col1:
        st.metric("Revenue Growth", f"{ass['revenue_growth_5yr']:.1%}")
    with a_col2:
        st.metric("Terminal Growth", f"{ass['terminal_growth']:.1%}")
    with a_col3:
        st.metric("Discount Rate", f"{ass['discount_rate']:.1%}")
    with a_col4:
        st.metric("Margin Δ/yr", f"{ass['margin_improvement']:+.1%}")

    st.caption(
        "⚠️ DCF is highly sensitive to assumptions. This is a simplified model — "
        "small changes in growth or discount rates produce large changes in fair value. "
        "Use as one input among many, not a definitive answer."
    )
