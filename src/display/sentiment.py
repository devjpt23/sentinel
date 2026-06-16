"""
Sentiment analysis and display components.
Keyword-based news sentiment + analyst consensus visualizations.
"""
import streamlit as st
from typing import Dict, Any, List


# ─── Keyword-based Sentiment Analysis ─────────────────────────
POSITIVE_WORDS = {
    "profit", "profits", "profitable", "growth", "growing", "surge", "surges", "surging",
    "rally", "rallies", "beat", "beats", "beating", "upgrade", "upgrades", "upgraded",
    "buy", "bullish", "strong", "record", "records", "rise", "rises", "rising",
    "gain", "gains", "gained", "positive", "opportunity", "opportunities",
    "innovation", "launch", "launches", "launched", "expansion", "expand", "expanding",
    "outperform", "outperforms", "outperformed", "boost", "boosts", "boosted",
    "recovery", "recovering", "rebound", "momentum", "breakthrough",
    "dividend", "buyback", "buybacks", "acquisition",
}

NEGATIVE_WORDS = {
    "loss", "losses", "decline", "declines", "declining", "drop", "drops", "dropping",
    "crash", "crashes", "crashed", "fear", "downgrade", "downgrades", "downgraded",
    "sell", "selling", "bearish", "weak", "weakness", "risk", "risks", "risky",
    "warning", "warn", "warns", "warned", "layoff", "layoffs", "investigation",
    "lawsuit", "lawsuits", "debt", "bankruptcy", "plunge", "plunges", "plunging",
    "underperform", "underperforms", "underperformed", "cut", "cuts", "cutting",
    "volatility", "volatile", "uncertainty", "sanction", "sanctions",
    "default", "delisting", "fraud", "probe", "crisis",
}


def analyze_news_sentiment(news_items: List[dict]) -> Dict[str, Any]:
    """Analyze news headlines and summaries for sentiment using keyword counting.

    Returns a dict with:
        - positive_count, neutral_count, negative_count
        - total_count
        - positive_pct
        - verdict: 'Positive' | 'Mixed' | 'Negative'
        - verdict_color: green | yellow | red
    """
    if not news_items:
        return {
            "positive_count": 0,
            "neutral_count": 0,
            "negative_count": 0,
            "total_count": 0,
            "positive_pct": 0,
            "verdict": "No News",
            "verdict_color": "#888888",
        }

    positive = 0
    negative = 0
    neutral = 0

    for item in news_items:
        title = (item.get("title") or "").lower()
        summary = (item.get("summary") or "").lower()
        text = f"{title} {summary}"

        # Count positive and negative keyword matches
        pos_count = sum(1 for word in POSITIVE_WORDS if word in text)
        neg_count = sum(1 for word in NEGATIVE_WORDS if word in text)

        if pos_count > neg_count:
            positive += 1
        elif neg_count > pos_count:
            negative += 1
        else:
            neutral += 1

    total = positive + neutral + negative
    pos_pct = positive / total * 100 if total > 0 else 0

    if pos_pct >= 50:
        verdict = "Positive"
        verdict_color = "#00C853"
    elif pos_pct >= 25:
        verdict = "Mixed"
        verdict_color = "#FFD600"
    else:
        verdict = "Negative"
        verdict_color = "#FF1744"

    return {
        "positive_count": positive,
        "neutral_count": neutral,
        "negative_count": negative,
        "total_count": total,
        "positive_pct": pos_pct,
        "verdict": verdict,
        "verdict_color": verdict_color,
    }


def render_sentiment_meter(sentiment: Dict[str, Any]):
    """Render a horizontal sentiment bar showing news tone."""
    if sentiment["total_count"] == 0:
        st.markdown(
            '<div style="color: #484F58; font-size: 0.85rem; padding: 10px 0;">'
            '📰 No recent news to analyze sentiment</div>',
            unsafe_allow_html=True,
        )
        return

    pos = sentiment["positive_count"]
    neu = sentiment["neutral_count"]
    neg = sentiment["negative_count"]
    total = sentiment["total_count"]
    verdict = sentiment["verdict"]
    color = sentiment["verdict_color"]

    # Calculate bar widths
    pos_w = (pos / total) * 100 if total > 0 else 0
    neu_w = (neu / total) * 100 if total > 0 else 0
    neg_w = (neg / total) * 100 if total > 0 else 0

    st.markdown(
        f'<div style="margin: 0 0 12px 0;">'
        f'<span style="color: {color}; font-weight: 700;">'
        f'📰 Recent news tone is {verdict}</span>'
        f'<span style="color: #8B949E; font-size: 0.8rem; margin-left: 8px;">'
        f'({pos} positive, {neu} neutral, {neg} negative)'
        f'</span>'
        f'</div>',
        unsafe_allow_html=True,
    )

    # Bar chart using pure CSS
    st.markdown(
        f'<div style="display: flex; width: 100%; height: 8px; border-radius: 4px; '
        f'overflow: hidden; background: #21262D; margin-bottom: 16px;">'
        + (f'<div style="width: {pos_w}%; background: #00C853; height: 100%;"></div>' if pos_w > 0 else "")
        + (f'<div style="width: {neu_w}%; background: #484F58; height: 100%;"></div>' if neu_w > 0 else "")
        + (f'<div style="width: {neg_w}%; background: #FF1744; height: 100%;"></div>' if neg_w > 0 else "")
        + f'</div>',
        unsafe_allow_html=True,
    )


def render_analyst_consensus(analyst_data: Dict[str, Any], company_name: str):
    """Render analyst price targets and recommendations in a 2-column card layout."""
    if not analyst_data:
        st.markdown(
            '<div style="color: #484F58; font-size: 0.85rem; padding: 10px 0;">'
            '🎯 No analyst coverage data available for this stock</div>',
            unsafe_allow_html=True,
        )
        return

    has_targets = "price_targets" in analyst_data
    has_recs = "recommendations" in analyst_data

    if not has_targets and not has_recs:
        st.markdown(
            '<div style="color: #484F58; font-size: 0.85rem; padding: 10px 0;">'
            '🎯 No analyst data available</div>',
            unsafe_allow_html=True,
        )
        return

    col1, col2 = st.columns(2)

    # ── Column 1: Price Target ──────────────────────────
    with col1:
        st.markdown(
            '<div style="color: #8B949E; font-size: 0.75rem; text-transform: uppercase; '
            'letter-spacing: 0.05em; margin-bottom: 8px;">🎯 Price Target</div>',
            unsafe_allow_html=True,
        )

        if has_targets:
            pt = analyst_data["price_targets"]
            current = pt.get("current")
            low = pt.get("low")
            mean = pt.get("mean")
            high = pt.get("high")
            upside = pt.get("upside_pct")

            # Render the price target bar if we have enough data
            if current and low and high and high > low:
                # Position current price on the low→high range as percentage
                pos_pct = ((current - low) / (high - low)) * 100
                pos_pct = max(0, min(100, pos_pct))

                # Mean target position
                mean_pct = ((mean - low) / (high - low)) * 100 if mean else 50
                mean_pct = max(0, min(100, mean_pct))

                st.markdown(
                    f'<div style="margin-bottom: 10px;">'
                    f'<div style="display: flex; justify-content: space-between; '
                    f'font-size: 0.75rem; color: #8B949E; margin-bottom: 4px;">'
                    f'<span>Low ${low:.0f}</span>'
                    f'<span>Mean ${mean:.0f}</span>'
                    f'<span>High ${high:.0f}</span>'
                    f'</div>'
                    f'<div style="position: relative; height: 24px; background: #21262D; '
                    f'border-radius: 6px; overflow: visible; margin: 4px 0 8px 0;">'
                    # Current price marker
                    f'<div style="position: absolute; left: {pos_pct}%; top: 0; '
                    f'transform: translateX(-50%);">'
                    f'<div style="width: 0; height: 0; border-left: 6px solid transparent; '
                    f'border-right: 6px solid transparent; border-top: 8px solid #58A6FF; '
                    f'margin: 0 auto;"></div>'
                    f'</div>'
                    # Mean target marker (diamond shape via smaller triangle)
                    f'<div style="position: absolute; left: {mean_pct}%; bottom: 0; '
                    f'transform: translateX(-50%);">'
                    f'<div style="width: 0; height: 0; border-left: 5px solid transparent; '
                    f'border-right: 5px solid transparent; border-bottom: 7px solid #FFD600; '
                    f'margin: 0 auto;"></div>'
                    f'</div>'
                    f'</div>'
                    f'</div>',
                    unsafe_allow_html=True,
                )

                # Upside/downside verdict
                if upside is not None:
                    upside_color = "#00C853" if upside > 5 else "#FFD600" if upside > -5 else "#FF1744"
                    upside_label = f"{upside:+.0f}%" if abs(upside) >= 0.5 else "flat"
                    st.markdown(
                        f'<div style="font-size: 1.1rem; font-weight: 700; color: {upside_color};">'
                        f'Current: ${current:.2f} &nbsp;→&nbsp; Target: {upside_label}'
                        f'</div>',
                        unsafe_allow_html=True,
                    )
            elif current and mean:
                upside = ((mean - current) / current) * 100 if current > 0 else 0
                upside_color = "#00C853" if upside > 5 else "#FFD600" if upside > -5 else "#FF1744"
                st.markdown(
                    f'<div style="font-size: 1.1rem; font-weight: 700; color: {upside_color};">'
                    f'Current: ${current:.2f} &nbsp;→&nbsp; Target: ${mean:.0f} ({upside:+.0f}%)'
                    f'</div>',
                    unsafe_allow_html=True,
                )
            else:
                st.markdown(
                    '<div style="color: #484F58; font-size: 0.85rem;">'
                    'Price target data incomplete</div>',
                    unsafe_allow_html=True,
                )
        else:
            st.markdown(
                '<div style="color: #484F58; font-size: 0.85rem;">'
                'No price target data available</div>',
                unsafe_allow_html=True,
            )

    # ── Column 2: Recommendations ───────────────────────
    with col2:
        st.markdown(
            '<div style="color: #8B949E; font-size: 0.75rem; text-transform: uppercase; '
            'letter-spacing: 0.05em; margin-bottom: 8px;">💡 Analyst Consensus</div>',
            unsafe_allow_html=True,
        )

        # ── OpenBB-enriched: recommendation score + number of analysts ──
        num_analysts = analyst_data.get("num_analysts")
        rec_mean = analyst_data.get("recommendation_mean")
        if num_analysts or rec_mean:
            meta_parts = []
            if num_analysts:
                meta_parts.append(f"📊 {num_analysts} analysts covering")
            if rec_mean is not None:
                # 1.0 = Strong Buy, 5.0 = Strong Sell
                if rec_mean <= 1.5:
                    rec_label = "Strong Buy"
                    rec_color = "#00C853"
                elif rec_mean <= 2.0:
                    rec_label = "Buy"
                    rec_color = "#00C853"
                elif rec_mean <= 2.5:
                    rec_label = "Moderate Buy"
                    rec_color = "#69F0AE"
                elif rec_mean <= 3.5:
                    rec_label = "Hold"
                    rec_color = "#FFD600"
                elif rec_mean <= 4.0:
                    rec_label = "Moderate Sell"
                    rec_color = "#FF9800"
                else:
                    rec_label = "Sell"
                    rec_color = "#FF1744"
                meta_parts.append(
                    f'<span style="color: {rec_color}; font-weight: 600;">{rec_label} ({rec_mean:.1f}/5)</span>'
                )
            if meta_parts:
                st.markdown(
                    f'<div style="font-size: 0.8rem; color: #8B949E; margin-bottom: 8px;">'
                    f'{" · ".join(meta_parts)}</div>',
                    unsafe_allow_html=True,
                )

        if has_recs:
            rec = analyst_data["recommendations"]
            total = rec.get("total", 0)
            buys = rec.get("buys", 0)
            holds = rec.get("hold", 0)
            sells = rec.get("sells", 0)
            verdict = rec.get("verdict", "N/A")
            verdict_color = rec.get("verdict_color", "#888888")

            if total > 0:
                buy_w = (buys / total) * 100
                hold_w = (holds / total) * 100
                sell_w = (sells / total) * 100

                st.markdown(
                    f'<div style="font-size: 1.2rem; font-weight: 700; color: {verdict_color}; '
                    f'margin-bottom: 8px;">{verdict}</div>',
                    unsafe_allow_html=True,
                )

                st.markdown(
                    f'<div style="margin-bottom: 6px; font-size: 0.8rem; color: #C9D1D9;">'
                    f'<span style="color: #00C853;">●</span> Buy: {buys} &nbsp;&nbsp;'
                    f'<span style="color: #FFD600;">●</span> Hold: {holds} &nbsp;&nbsp;'
                    f'<span style="color: #FF1744;">●</span> Sell: {sells}'
                    f'</div>',
                    unsafe_allow_html=True,
                )

                # Recommendation bar
                st.markdown(
                    f'<div style="display: flex; width: 100%; height: 8px; border-radius: 4px; '
                    f'overflow: hidden; background: #21262D;">'
                    + (f'<div style="width: {buy_w}%; background: #00C853; height: 100%;"></div>' if buy_w > 0 else "")
                    + (f'<div style="width: {hold_w}%; background: #FFD600; height: 100%;"></div>' if hold_w > 0 else "")
                    + (f'<div style="width: {sell_w}%; background: #FF1744; height: 100%;"></div>' if sell_w > 0 else "")
                    + f'</div>',
                    unsafe_allow_html=True,
                )

                # Plain-English summary
                if buys > holds + sells:
                    summary = f"Most analysts recommend buying {company_name} — {buys} out of {total} say Buy"
                elif holds >= buys and holds >= sells:
                    summary = f"Analysts are divided on {company_name} — {holds} say Hold, with a slight lean toward {'Buy' if buys >= sells else 'Sell'}"
                else:
                    summary = f"Analysts are cautious on {company_name} — {sells} recommend selling"

                st.markdown(
                    f'<div style="color: #8B949E; font-size: 0.8rem; margin-top: 8px; '
                    f'line-height: 1.4;">{summary}</div>',
                    unsafe_allow_html=True,
                )
            else:
                st.markdown(
                    '<div style="color: #484F58;">Insufficient recommendation data</div>',
                    unsafe_allow_html=True,
                )
        else:
            st.markdown(
                '<div style="color: #484F58; font-size: 0.85rem;">'
                'No recommendation data available</div>',
                unsafe_allow_html=True,
            )


def render_institutional_activity(inst_data: Dict[str, Any]):
    """Render institutional holders section showing big money positioning."""
    if not inst_data:
        st.markdown(
            '<div style="color: #484F58; font-size: 0.85rem; padding: 10px 0;">'
            '🏛️ No institutional ownership data available</div>',
            unsafe_allow_html=True,
        )
        return

    holders = inst_data.get("holders", [])
    verdict = inst_data.get("verdict")
    verdict_color = inst_data.get("verdict_color", "#888888")
    verdict_text = inst_data.get("verdict_text", "")

    if not holders:
        st.markdown(
            '<div style="color: #484F58; font-size: 0.85rem; padding: 10px 0;">'
            '🏛️ No institutional holders data available</div>',
            unsafe_allow_html=True,
        )
        return

    # Verdict header
    if verdict:
        st.markdown(
            f'<div style="margin-bottom: 12px;">'
            f'<span style="font-weight: 700; color: {verdict_color}; font-size: 1rem;">'
            f'🏛️ Smart Money: {verdict}</span>'
            f'<span style="color: #8B949E; font-size: 0.8rem; margin-left: 8px;">{verdict_text}</span>'
            f'</div>',
            unsafe_allow_html=True,
        )

    # Build holder cards
    cols = st.columns(min(len(holders), 5))
    for i, holder in enumerate(holders[:5]):
        with cols[i]:
            pct_change = holder.get("pct_change")
            if pct_change is not None:
                if pct_change > 1:
                    change_color = "#00C853"
                    change_emoji = "📈"
                elif pct_change < -1:
                    change_color = "#FF1744"
                    change_emoji = "📉"
                else:
                    change_color = "#8B949E"
                    change_emoji = "➡️"
                change_str = f"{pct_change:+.1f}%"
            else:
                change_color = "#8B949E"
                change_emoji = ""
                change_str = "N/A"

            pct_held = holder.get("pct_held")
            held_str = f"{pct_held:.2f}%" if pct_held is not None else ""

            st.markdown(
                f'<div class="inst-card">'
                f'<div class="inst-name" title="{holder["name"]}">{holder["name"][:25]}</div>'
                f'<div class="inst-held">{held_str} of float</div>'
                f'<div class="inst-change" style="color: {change_color};">'
                f'{change_emoji} {change_str}</div>'
                f'</div>',
                unsafe_allow_html=True,
            )
