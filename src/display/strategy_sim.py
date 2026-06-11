"""
Strategy Simulation UI — config panel, distribution chart, stats table.
"""

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from typing import Dict, Any, Optional

from src.strategy.engine import compute_indicators, run_batch


def render_strategy_lab(ticker: str, price_data: Optional[pd.DataFrame],
                        data: Dict[str, Any]):
    """Main Strategy Lab entry point — config + simulation + results.

    Args:
        ticker: Stock ticker
        price_data: DataFrame with OHLCV data (from yfinance history)
        data: Full company data dict (for fundamental scores)
    """
    st.markdown('<h2 style="color: #58A6FF;">🎯 Strategy Lab</h2>', unsafe_allow_html=True)
    st.markdown(
        "Design a buy/sell strategy using the sliders below. "
        "The simulation will test your rules against *past* price data using "
        "thousands of random entry points — showing what outcomes you could expect."
    )

    if price_data is None or price_data.empty:
        st.warning("No price data available for this ticker.")
        return

    # Compute indicators (with volume if available)
    vol = price_data["Volume"] if "Volume" in price_data.columns else None
    price_df = compute_indicators(price_data["Close"], vol)
    current_price = float(price_data["Close"].iloc[-1])

    health_score = data.get("health_score", 50)
    intrinsic_score = data.get("intrinsic_score", 50)
    company = data.get("company", {})
    name = company.get("name", ticker)

    # ─── Quality Summary (static) ───
    st.markdown("### 🏢 Stock Quality Profile")
    q_cols = st.columns(3)
    with q_cols[0]:
        st.metric("Health Score", f"{health_score}/100",
                  help="Fundamental strength of the company")
    with q_cols[1]:
        st.metric("Intrinsic Worth", f"{intrinsic_score}/100",
                  help="How cheap the stock is on an absolute basis")
    with q_cols[2]:
        st.metric("Current Price", f"${current_price:.2f}")

    # ─── Config Panel ───
    st.markdown("### ⚙️ Strategy Settings")

    col1, col2 = st.columns(2)

    with col1:
        st.markdown("**📥 Entry Rules** (buy when ALL are true)")
        min_rsi = st.slider("RSI must be below", 20, 70, 40, 5,
                            help="Stock must be this oversold. Lower = more extreme. RSI < 30 is typical oversold.")
        min_pullback = st.slider("Pullback from 52w high ≥", 1, 40, 10, 1, format="%%",
                                 help="Stock must have fallen at least this much from its 52-week high.")
        above_200ma = st.checkbox("Must be above 200-day MA", value=False,
                                  help="Only buy if price is above the long-term trend line. Safer but fewer opportunities.")
        require_volume = st.checkbox("Require volume confirmation", value=False,
                                     help="Only enter when volume exceeds 1.5x the 20-day average. "
                                          "Volume confirms price — entries on low-volume pullbacks are less reliable.")
        st.markdown("**🔬 Fundamental Quality Filter** (optional)")
        min_health = st.slider("Min Health Score", 0, 100, 50, 5,
                               help="Only enter if the company's fundamental health meets this threshold. "
                                    "Combines F-Score, Z-Score, and profitability.")
        min_intrinsic = st.slider("Min Intrinsic Value Score", 0, 100, 40, 5,
                                  help="Only enter if the stock is sufficiently undervalued on an absolute basis. "
                                       "Based on Graham Number, DCF, and FCF yield.")

    with col2:
        st.markdown("**📤 Exit Rules**")
        take_profit = st.slider("Take profit at", 5, 100, 25, 5, format="%%",
                                help="Sell after this gain.")
        stop_loss = st.slider("Stop loss at", 5, 50, 15, 5, format="%%",
                              help="Sell after this loss.")
        max_hold = st.slider("Max hold time", 30, 730, 365, 30, "days",
                             help="Sell after this many days even if no target was hit.")

    n_simulations = st.slider("Simulation runs", 500, 10000, 2000, 500,
                              help="More runs = more accurate distribution. 2000+ recommended.")

    # Per-position assumption
    position_size = st.number_input("Position size (% of portfolio per trade)",
                                    min_value=1, max_value=100, value=10, step=1)

    st.markdown("---")

    # ─── Run Simulation ───
    params = {
        "max_rsi": min_rsi,
        "min_pullback": float(min_pullback),
        "above_200ma": above_200ma,
        "min_volume_ratio": 1.5 if require_volume else 0,
        "min_health_score": min_health,
        "min_intrinsic_score": min_intrinsic,
        "_health_score": health_score,
        "_intrinsic_score": intrinsic_score,
        "take_profit_pct": take_profit / 100,
        "stop_loss_pct": stop_loss / 100,
        "max_hold_days": max_hold,
    }

    if st.button("▶️ Run Simulation", type="primary", use_container_width=True):
        with st.spinner(f"Running {n_simulations} simulated trades on {ticker}..."):
            result = run_batch(price_df, params, n_runs=n_simulations)

        if result.get("error"):
            st.error(result["error"])
            return

        trades = result["trades"]
        stats = result["stats"]

        # ─── Results ───
        st.markdown("---")
        st.markdown(f'<h3 style="color: #58A6FF;">📊 Simulation Results — {len(trades)} Trades</h3>',
                    unsafe_allow_html=True)

        # Summary cards
        r_cols = st.columns(5)
        with r_cols[0]:
            delta = f"{stats['median_return']:+.1f}%"
            st.metric("Median Return", delta,
                      help="Half of trades did better, half did worse")
        with r_cols[1]:
            st.metric("Win Rate", f"{stats['win_rate']}%",
                      help="Percentage of profitable trades")
        with r_cols[2]:
            st.metric("Best/Worst", f"{stats['best_return']:+.0f}% / {stats['worst_return']:+.0f}%",
                      help="Best and worst individual trade returns")
        with r_cols[3]:
            st.metric("Avg Drawdown", f"{stats['median_drawdown']:.1f}%",
                      help="Typical peak-to-trough decline during trades")
        with r_cols[4]:
            st.metric("Avg Sharpe", f"{stats['avg_sharpe']:.2f}",
                      help="Risk-adjusted return. 0.5+ = decent, 1.0+ = great")

        # ─── Distribution Chart ───
        st.markdown("### 📈 Return Distribution")
        returns = [t["return_pct"] for t in trades]
        exit_reasons = [t["exit_reason"] for t in trades]

        fig = go.Figure()

        # Histogram
        fig.add_trace(go.Histogram(
            x=returns,
            nbinsx=50,
            marker_color="#58A6FF",
            marker_line_color="#0D1117",
            marker_line_width=0.5,
            name="Trades",
            hovertemplate="Return: %{x:+.1f}%<br>Count: %{y}<extra></extra>",
        ))

        # Median line
        median_val = stats["median_return"]
        fig.add_vline(x=median_val, line_dash="dash", line_color="#FFD600",
                      annotation_text=f"Median: {median_val:+.1f}%",
                      annotation_font_color="#FFD600")

        # Zero line
        fig.add_vline(x=0, line_color="#484F58", line_width=1)

        fig.update_layout(
            height=350,
            margin=dict(l=10, r=10, t=10, b=10),
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            xaxis=dict(title="Return %", showgrid=True, gridcolor="#21262D", color="#8B949E"),
            yaxis=dict(title="# of Trades", showgrid=True, gridcolor="#21262D", color="#8B949E"),
            hovermode="x",
            bargap=0.05,
        )
        st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})

        # ─── Exit Reason Pie ───
        reason_counts = {}
        for r in exit_reasons:
            reason_counts[r] = reason_counts.get(r, 0) + 1

        pie_colors = {"take_profit": "#00C853", "stop_loss": "#FF1744",
                      "max_hold": "#58A6FF"}

        fig2 = go.Figure(data=[go.Pie(
            labels=list(reason_counts.keys()),
            values=list(reason_counts.values()),
            marker_colors=[pie_colors.get(k, "#8B949E") for k in reason_counts.keys()],
            textinfo="label+percent",
            textfont=dict(color="#C9D1D9", size=12),
            hovertemplate="%{label}<br>%{percent}<extra></extra>",
        )])
        fig2.update_layout(
            height=250,
            margin=dict(l=10, r=10, t=10, b=10),
            paper_bgcolor="rgba(0,0,0,0)",
            showlegend=False,
        )

        # ─── Portfolio Estimate ───
        port_value = 10000  # assume $10k starting
        mean_return_decimal = stats["mean_return"] / 100
        expected_per_trade = port_value * (position_size / 100) * mean_return_decimal
        expected_with_wins = port_value * (position_size / 100) * stats["win_rate"] / 100 * (stats["median_return"] / 100 if stats["median_return"] > 0 else stats["mean_return"] / 100)

        col_pie, col_portfolio = st.columns([1, 2])

        with col_pie:
            st.markdown("### 🏁 Exit Reasons")
            st.plotly_chart(fig2, use_container_width=True, config={"displayModeBar": False})

        with col_portfolio:
            st.markdown("### 💼 What This Means for a $10k Portfolio")
            st.markdown(
                f'<div class="story-box" style="font-size: 0.95rem;">'
                f"With a **{position_size}%** position size and **{stats['win_rate']}%** win rate:<br><br>"
                f"📈 **Per winning trade:** ~+{stats['pctile_75']:+.1f}% (top 25% of outcomes)<br>"
                f"📉 **Per losing trade:** ~{stats['pctile_25']:+.1f}% (worst 25%)<br><br>"
                f"⏱️ **Median hold:** {stats['median_hold_days']} days<br><br>"
                f"<strong style='color: #FFD600;'>The range of likely outcomes:</strong><br>"
                f"📍 10th percentile: {stats['pctile_10']:+.1f}% (worst 1 in 10)<br>"
                f"📍 Median: {stats['median_return']:+.1f}%<br>"
                f"📍 90th percentile: {stats['pctile_90']:+.1f}% (best 1 in 10)<br><br>"
                f"<span style='color: #8B949E; font-size: 0.85rem;'>"
                f"Only {100 - stats['win_rate']:.0f}% of trades ended in a loss. "
                f"The average risk-adjusted return (Sharpe) was {stats['avg_sharpe']:.2f}."
                f"</span>"
                f'</div>',
                unsafe_allow_html=True
            )

        # ─── Recent Trades Table ───
        st.markdown("### 📋 Sample Trades (last 20)")
        trades_df = pd.DataFrame(trades[-20:])
        trades_df = trades_df[["entry_date", "entry_price", "exit_date", "exit_price",
                                "return_pct", "hold_days", "exit_reason"]]

        def color_return(val):
            if pd.notna(val) and val > 0:
                return f"<span style='color: #00C853;'>{val:+.1f}%</span>"
            elif pd.notna(val):
                return f"<span style='color: #FF1744;'>{val:+.1f}%</span>"
            return ""

        styled_rows = ""
        for _, row in trades_df.iterrows():
            ret_str = color_return(row.get("return_pct"))
            reason = row.get("exit_reason", "")
            reason_colors = {"take_profit": "#00C853", "stop_loss": "#FF1744", "max_hold": "#58A6FF"}
            rcolor = reason_colors.get(reason, "#8B949E")
            styled_rows += (
                f"<tr>"
                f"<td style='padding: 6px 10px; border-bottom: 1px solid #21262D;'>{str(row.get('entry_date', ''))[:10]}</td>"
                f"<td style='padding: 6px 10px; border-bottom: 1px solid #21262D;'>${row.get('entry_price', 0):.2f}</td>"
                f"<td style='padding: 6px 10px; border-bottom: 1px solid #21262D;'>{str(row.get('exit_date', ''))[:10]}</td>"
                f"<td style='padding: 6px 10px; border-bottom: 1px solid #21262D;'>${row.get('exit_price', 0):.2f}</td>"
                f"<td style='padding: 6px 10px; border-bottom: 1px solid #21262D;'>{ret_str}</td>"
                f"<td style='padding: 6px 10px; border-bottom: 1px solid #21262D;'>{int(row.get('hold_days', 0))}d</td>"
                f"<td style='padding: 6px 10px; border-bottom: 1px solid #21262D; color: {rcolor};'>{reason}</td>"
                f"</tr>"
            )

        st.markdown(
            f'<table style="width: 100%; font-size: 0.85rem; border-collapse: collapse;">'
            f"<thead><tr style='color: #8B949E;'>"
            f"<th style='padding: 8px 10px; border-bottom: 1px solid #30363D;'>Entry</th>"
            f"<th style='padding: 8px 10px; border-bottom: 1px solid #30363D;'>Price</th>"
            f"<th style='padding: 8px 10px; border-bottom: 1px solid #30363D;'>Exit</th>"
            f"<th style='padding: 8px 10px; border-bottom: 1px solid #30363D;'>Price</th>"
            f"<th style='padding: 8px 10px; border-bottom: 1px solid #30363D;'>Return</th>"
            f"<th style='padding: 8px 10px; border-bottom: 1px solid #30363D;'>Hold</th>"
            f"<th style='padding: 8px 10px; border-bottom: 1px solid #30363D;'>Reason</th>"
            f"</tr></thead>"
            f"<tbody>{styled_rows}</tbody>"
            f"</table>",
            unsafe_allow_html=True
        )

        # ─── Strategy Commentary ───
        st.markdown("### 💡 Strategy Assessment")
        win_rate = stats["win_rate"]
        sharpe = stats["avg_sharpe"]
        med_ret = stats["median_return"]

        parts = [f"**Your strategy for {name}**"]

        if win_rate > 65:
            parts.append(f"has a strong win rate of {win_rate:.0f}% — most trades are profitable.")
        elif win_rate > 50:
            parts.append(f"wins {win_rate:.0f}% of the time — slightly better than a coin flip.")
        else:
            parts.append(f"wins only {win_rate:.0f}% of the time — most trades lose money.")

        if med_ret > 15:
            parts.append(f"The median trade returns {med_ret:+.1f}%, which is solid.")
        elif med_ret > 5:
            parts.append(f"The median trade returns {med_ret:+.1f}%.")
        elif med_ret < 0:
            parts.append(f"The median trade loses money ({med_ret:+.1f}%). Consider tightening entry rules.")
        else:
            parts.append(f"The median trade returns {med_ret:+.1f}%.")

        if sharpe > 0.8:
            parts.append(f"The Sharpe ratio of {sharpe:.2f} suggests excellent risk-adjusted returns.")
        elif sharpe > 0.3:
            parts.append(f"The Sharpe ratio of {sharpe:.2f} is decent — returns justify the risk.")
        else:
            parts.append(f"The Sharpe ratio of {sharpe:.2f} is low — risk may not be worth the return.")

        # Specific recommendations
        suggestions = []
        if win_rate < 40 and med_ret < 0:
            suggestions.append("🔧 **Try loosening entry rules:** increase max RSI or decrease min pullback to find more opportunities.")
        if stats["worst_drawdown"] < -25:
            suggestions.append("🔧 **Reduce position size or tighten stop loss** to limit worst-case drawdown.")
        if take_profit < 15 and win_rate > 60:
            suggestions.append("🔧 **Consider raising take profit target** — your high win rate suggests you're leaving gains on the table.")
        if stop_loss > 20 and stats["worst_drawdown"] < -30:
            suggestions.append("🔧 **Tighten your stop loss** to limit downside.")
        if max_hold < 90 and win_rate < 40:
            suggestions.append("🔧 **Increase max hold time** — some trades may need more time to work out.")

        if suggestions:
            parts.append("")
            parts.extend(suggestions)
        else:
            parts.append("✅ The strategy parameters look reasonable for this stock.")

        st.markdown(
            f'<div class="story-box" style="font-size: 0.95rem;">{" ".join(parts)}</div>',
            unsafe_allow_html=True
        )

        # ─── Save Strategy ───
        st.markdown("---")
        strategy_name = st.text_input("Name this strategy to compare later:", placeholder="e.g., Aggressive Growth, Conservative Value")
        if strategy_name and st.button("💾 Save Strategy", use_container_width=True):
            saved = {
                "name": strategy_name,
                "ticker": ticker,
                "params": params,
                "stats": stats,
            }
            if "saved_strategies" not in st.session_state:
                st.session_state.saved_strategies = []
            st.session_state.saved_strategies.append(saved)
            st.success(f"Strategy '{strategy_name}' saved! (for this session)")
            st.rerun()

    # ─── Saved Strategies Comparison ───
    if "saved_strategies" in st.session_state and st.session_state.saved_strategies:
        st.markdown("---")
        st.markdown("### 📊 Saved Strategies")

        # Build comparison table
        comp_data = []
        for s in st.session_state.saved_strategies:
            comp_data.append({
                "Name": s["name"],
                "Ticker": s["ticker"],
                "Win Rate": f"{s['stats']['win_rate']}%",
                "Med Return": f"{s['stats']['median_return']:+.1f}%",
                "Sharpe": s["stats"]["avg_sharpe"],
                "Avg Drawdown": f"{s['stats']['median_drawdown']:.1f}%",
                "Runs": s["stats"]["total_runs"],
            })

        if comp_data:
            comp_df = pd.DataFrame(comp_data)
            # Highlight best row
            best_idx = comp_df["Sharpe"].idxmax() if "Sharpe" in comp_df.columns else -1

            rows_html = ""
            for i, row in comp_df.iterrows():
                highlight = " style='background: #1A2332;'" if i == best_idx else ""
                ret_str = str(row['Med Return'])
                ret_color = '#00C853' if '+' in ret_str else '#FF1744'
                rows_html += (
                    f"<tr{highlight}>"
                    f"<td style='padding: 8px 12px; border-bottom: 1px solid #21262D;'><strong>{row['Name']}</strong></td>"
                    f"<td style='padding: 8px 12px; border-bottom: 1px solid #21262D;'>{row['Ticker']}</td>"
                    f"<td style='padding: 8px 12px; border-bottom: 1px solid #21262D;'>{row['Win Rate']}</td>"
                    f"<td style='padding: 8px 12px; border-bottom: 1px solid #21262D; color: {ret_color};'>{ret_str}</td>"
                    f"<td style='padding: 8px 12px; border-bottom: 1px solid #21262D;'>{row['Sharpe']}</td>"
                    f"<td style='padding: 8px 12px; border-bottom: 1px solid #21262D;'>{row['Avg Drawdown']}</td>"
                    f"</tr>"
                )

            st.markdown(
                f'<table style="width: 100%; font-size: 0.85rem; border-collapse: collapse;">'
                f"<thead><tr style='color: #8B949E;'>"
                f"<th style='padding: 8px 12px; border-bottom: 1px solid #30363D;'>Name</th>"
                f"<th style='padding: 8px 12px; border-bottom: 1px solid #30363D;'>Ticker</th>"
                f"<th style='padding: 8px 12px; border-bottom: 1px solid #30363D;'>Win Rate</th>"
                f"<th style='padding: 8px 12px; border-bottom: 1px solid #30363D;'>Med Return</th>"
                f"<th style='padding: 8px 12px; border-bottom: 1px solid #30363D;'>Sharpe</th>"
                f"<th style='padding: 8px 12px; border-bottom: 1px solid #30363D;'>Drawdown</th>"
                f"</tr></thead>"
                f"<tbody>{rows_html}</tbody>"
                f"</table>"
                f'<p style="color: #484F58; font-size: 0.75rem; margin-top: 6px;">Highlighted row = best Sharpe ratio</p>',
                unsafe_allow_html=True
            )

            if st.button("🗑️ Clear Saved Strategies", key="clear_strats"):
                st.session_state.saved_strategies = []
                st.rerun()
