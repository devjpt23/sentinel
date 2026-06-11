"""
Live stock price ticker — server-side fragment that auto-refreshes every 5 seconds.
No CORS issues, no client-side API keys needed.
"""

import streamlit as st
from typing import Optional
from datetime import datetime


def render_live_ticker(ticker: str, initial_price: Optional[float] = None,
                       initial_change_pct: Optional[float] = None):
    """Render a live-updating price ticker that refreshes every 5 seconds.

    Uses Streamlit's @st.fragment with run_every for periodic server-side refresh.
    The fragment re-fetches the current price from yfinance, avoiding the CORS
    issues that plagued the previous client-side JS approach.

    Args:
        ticker: Stock ticker symbol
        initial_price: Current price from the initial data fetch (shown on first render)
        initial_change_pct: Daily change % from initial data fetch
    """

    @st.fragment(run_every=5)
    def _ticker_fragment():
        # Fetch latest price server-side (bypasses CORS)
        try:
            import yfinance as yf
            t = yf.Ticker(ticker)
            info = t.info or {}

            price = info.get("currentPrice") or info.get("regularMarketPrice")
            prev_close = info.get("previousClose") or info.get("regularMarketPreviousClose")

            if price and prev_close and prev_close > 0:
                change_pct = ((price - prev_close) / prev_close) * 100
            else:
                price = initial_price
                change_pct = initial_change_pct

            market_state = info.get("marketState", "")
            if market_state == "REGULAR":
                status_text = "🟢 Market Open"
                status_color = "#00C853"
            elif market_state in ("PRE", "PREPRE"):
                status_text = "🟡 Pre-Market"
                status_color = "#FFD600"
            elif market_state in ("POST", "POSTPOST"):
                status_text = "🟡 After Hours"
                status_color = "#FFD600"
            else:
                status_text = "⚫ Market Closed"
                status_color = "#484F58"

        except Exception:
            price = initial_price
            change_pct = initial_change_pct
            status_text = "⚠️ Unavailable"
            status_color = "#FF6B7A"

        # Format for display
        if price:
            price_str = f"${price:.2f}"
        else:
            price_str = "—"

        if change_pct is not None:
            arrow = "▲" if change_pct >= 0 else "▼"
            change_color = "#00C853" if change_pct >= 0 else "#FF1744"
            change_str = f"{arrow} {change_pct:+.2f}%"
        else:
            change_color = "#8B949E"
            change_str = ""

        now = datetime.now().strftime("%H:%M:%S")

        st.markdown(f"""
        <div id="live-ticker-container" style="
            background: #161B22;
            border: 1px solid #30363D;
            border-radius: 10px;
            padding: 16px 24px;
            margin-bottom: 16px;
            display: flex;
            align-items: center;
            justify-content: space-between;
            font-family: -apple-system, BlinkMacSystemFont, sans-serif;
        ">
            <div style="display: flex; align-items: center; gap: 20px;">
                <span style="color: #8B949E; font-size: 0.85rem; font-weight: 600;">{ticker}</span>
                <span id="live-price" style="font-size: 2rem; font-weight: 700; color: #C9D1D9;">{price_str}</span>
                <span id="live-change" style="font-size: 1.1rem; font-weight: 600; color: {change_color};">{change_str}</span>
            </div>
            <div style="display: flex; align-items: center; gap: 12px;">
                <span style="font-size: 0.75rem; color: {status_color};">{status_text}</span>
                <span style="font-size: 0.7rem; color: #30363D;">●</span>
                <span style="font-size: 0.7rem; color: #484F58;">Updated {now}</span>
            </div>
        </div>
        """, unsafe_allow_html=True)

    _ticker_fragment()
