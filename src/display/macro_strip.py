"""
Market Macro Strip — compact horizontal banner showing 5 key macro indicators.
Renders a single row of tiny cards: VIX, S&P trend, yield curve, credit, dollar.
"""
import streamlit as st
from typing import Dict, Any


def render_macro_strip(macro: Dict[str, Any]):
    """Render a compact 5-indicator macro strip.

    Each indicator is a tiny card with an icon, value, verdict badge, and tooltip detail.
    Gracefully handles missing indicators (shows 'N/A').
    """
    if not macro:
        st.markdown(
            '<div style="color: #484F58; font-size: 0.8rem; text-align: center; '
            'padding: 12px;">🌐 Macro data unavailable — continuing with company analysis</div>',
            unsafe_allow_html=True,
        )
        return

    cols = st.columns(5)

    indicators = [
        ("vix", "😰", "Fear Gauge"),
        ("sp500", "📈", "S&P 500"),
        ("yield_curve", "📉", "Yield Curve"),
        ("credit", "💳", "Credit"),
        ("dollar", "💵", "Dollar"),
    ]

    for i, (key, icon, fallback_label) in enumerate(indicators):
        indicator = macro.get(key)
        with cols[i]:
            if indicator:
                _render_indicator_card(icon, indicator)
            else:
                st.markdown(
                    f'<div class="macro-card">'
                    f'<div class="macro-icon">{icon}</div>'
                    f'<div class="macro-label">{fallback_label}</div>'
                    f'<div class="macro-value" style="color: #484F58;">N/A</div>'
                    f'</div>',
                    unsafe_allow_html=True,
                )


def _render_indicator_card(icon: str, indicator: Dict[str, Any]):
    """Render a single macro indicator card."""
    label = indicator.get("label", "")
    verdict = indicator.get("verdict", "")
    color = indicator.get("color", "#888888")
    detail = indicator.get("detail", "")

    # Format the value for display
    value = indicator.get("value")
    if value is not None:
        if isinstance(value, float):
            if abs(value) < 10:
                val_str = f"{value:.2f}"
            elif abs(value) < 100:
                val_str = f"{value:.1f}"
            else:
                val_str = f"{value:,.0f}"
        else:
            val_str = str(value)
    else:
        val_str = "N/A"

    st.markdown(
        f'<div class="macro-card" title="{detail}">'
        f'<div class="macro-icon">{icon}</div>'
        f'<div class="macro-label">{label}</div>'
        f'<div class="macro-value">{val_str}</div>'
        f'<div class="macro-verdict" style="color: {color};">● {verdict}</div>'
        f'</div>',
        unsafe_allow_html=True,
    )
