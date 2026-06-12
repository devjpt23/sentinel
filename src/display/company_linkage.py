"""
Company linkage display — relationships between companies within a sector.

Renders relationship cards (table view), a Plotly network graph, an
ecosystem health dashboard, and auto-generated investment insight cards.

Called by sector_search.py to show the "Company Relationships" section.
"""

import math
import streamlit as st
import plotly.graph_objects as go

from src.data.company_links import get_relationships_in_group
from src.scoring.relationships import (
    compute_ecosystem_summary,
    generate_relationship_insights,
)


# ---------------------------------------------------------------------------
# Color / emoji mappings
# ---------------------------------------------------------------------------

TYPE_EMOJI = {
    "supplier": "⬆️",
    "customer": "⬇️",
    "competitor": "⚔️",
    "partner": "\U0001f91d",  # 🤝
    "investor": "\U0001f4b0",  # 💰
}

TYPE_COLORS = {
    "supplier": "#FFD600",
    "customer": "#58A6FF",
    "competitor": "#FF6B7A",
    "partner": "#00C853",
    "investor": "#C9D1D9",
}

EDGE_DASH = {
    "supplier": "solid",
    "customer": "solid",
    "competitor": "dash",
    "partner": "dot",
    "investor": "dashdot",
}


def _health_color(verdict: str) -> str:
    """Map a health verdict to the appʼs standard traffic-light color."""
    return {
        "Strong": "#00C853",
        "Moderate": "#FFD600",
        "Weak": "#FF1744",
    }.get(verdict, "#8B949E")


def _health_bg(verdict: str) -> str:
    """Translucent background tint for a health badge."""
    return {
        "Strong": "#00C85322",
        "Moderate": "#FFD60022",
        "Weak": "#FF174422",
    }.get(verdict, "#8B949E22")


def _ticker_health_badge(ticker: str, metrics_data: dict) -> str:
    """Return an HTML snippet for a health badge pill, or empty string if N/A."""
    entry = (metrics_data.get(ticker) or {})
    qh = entry.get("quick_health") or {}
    verdict = qh.get("verdict", "N/A")
    score = qh.get("score")
    if verdict == "N/A":
        return ""
    color = _health_color(verdict)
    bg = _health_bg(verdict)
    score_text = f" {score}/10" if score is not None else ""
    return (
        f'<span style="background:{bg}; color:{color}; font-size:0.68rem; '
        f'font-weight:600; padding:1px 7px; border-radius:8px; margin-left:6px; '
        f'white-space:nowrap;">{verdict}{score_text}</span>'
    )


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def render_sector_linkage(tickers: list[str], metrics_data: dict):
    """Render the relationship section for companies in a sector.

    Shows an ecosystem health dashboard, investment insight cards,
    a relationship table, and an interactive network graph.
    """
    relationships = get_relationships_in_group(tickers)

    if not relationships:
        st.markdown(
            '<div style="color: #8B949E; font-size: 0.9rem; padding: 30px 20px; '
            'text-align: center; background: #161B22; border: 1px solid #30363D; '
            'border-radius: 12px;">'
            "No curated relationships found for companies in this sector yet.<br>"
            '<span style="font-size: 0.8rem;">Relationships are manually curated '
            "— check back as we add more.</span>"
            "</div>",
            unsafe_allow_html=True,
        )
        return

    st.markdown(
        f"**{len(relationships)}** known "
        f"relationship{'s' if len(relationships) > 1 else ''} "
        f"between companies in this group."
    )

    # ── Ecosystem health dashboard ──
    _render_ecosystem_dashboard(relationships, metrics_data)

    # ── Investment insight cards ──
    insights = generate_relationship_insights(relationships, metrics_data)
    if insights:
        _render_insight_feed(insights)

    # ── Tab view: Table | Network Graph ──
    tab_table, tab_graph = st.tabs([
        "\U0001f4cb Relationship Table",
        "\U0001f578️ Relationship Map",
    ])

    with tab_table:
        _render_relationship_table(relationships, metrics_data)

    with tab_graph:
        _render_relationship_graph(relationships, metrics_data)


# ---------------------------------------------------------------------------
# Ecosystem health dashboard
# ---------------------------------------------------------------------------

def _render_ecosystem_dashboard(relationships: list[dict], metrics_data: dict):
    """Render a compact row of ecosystem health metric cards above the tabs."""
    eco = compute_ecosystem_summary(relationships, metrics_data)

    avg = eco["avg_health"]
    avg_color = _health_color(
        "Strong" if (avg or 0) >= 70 else ("Moderate" if (avg or 0) >= 40 else "Weak")
    )
    avg_display = f"{avg}/100" if avg is not None else "N/A"

    # Critical nodes display
    cn_list = eco.get("critical_nodes", [])[:2]
    cn_text = ", ".join(n["ticker"] for n in cn_list) if cn_list else "None"

    # Competitor display
    comp_leader = eco.get("competitor_leader") or "—"
    comp_laggard = eco.get("competitor_laggard") or "—"

    cols = st.columns(3)

    with cols[0]:
        st.markdown(
            f'<div style="background:#161B22; border:1px solid #30363D; '
            f'border-radius:10px; padding:14px 16px; height:100%;">'
            f'<div style="color:#8B949E; font-size:0.7rem; text-transform:uppercase; '
            f'letter-spacing:0.5px; margin-bottom:6px;">🔗 Supply Chain</div>'
            f'<div style="color:{avg_color}; font-size:1.3rem; font-weight:700;">{avg_display}</div>'
            f'<div style="color:#8B949E; font-size:0.75rem; margin-top:2px;">avg ecosystem health</div>'
            f'<div style="color:#C9D1D9; font-size:0.75rem; margin-top:6px;">'
            f'<span style="color:#00C853;">{eco["strong_count"]} Strong</span> · '
            f'<span style="color:#FFD600;">{eco["moderate_count"]} Moderate</span> · '
            f'<span style="color:#FF1744;">{eco["weak_count"]} Weak</span>'
            f'</div>'
            f'</div>',
            unsafe_allow_html=True,
        )

    with cols[1]:
        comp_count = eco.get("competitor_count", 0)
        st.markdown(
            f'<div style="background:#161B22; border:1px solid #30363D; '
            f'border-radius:10px; padding:14px 16px; height:100%;">'
            f'<div style="color:#8B949E; font-size:0.7rem; text-transform:uppercase; '
            f'letter-spacing:0.5px; margin-bottom:6px;">⚔️ Competitive Field</div>'
            f'<div style="color:#C9D1D9; font-size:1.3rem; font-weight:700;">{comp_count}</div>'
            f'<div style="color:#8B949E; font-size:0.75rem; margin-top:2px;">competitors mapped</div>'
            f'<div style="color:#C9D1D9; font-size:0.75rem; margin-top:6px;">'
            f'Leader: <span style="color:#58A6FF;">{comp_leader}</span> · '
            f'Laggard: <span style="color:#8B949E;">{comp_laggard}</span>'
            f'</div>'
            f'</div>',
            unsafe_allow_html=True,
        )

    with cols[2]:
        st.markdown(
            f'<div style="background:#161B22; border:1px solid #30363D; '
            f'border-radius:10px; padding:14px 16px; height:100%;">'
            f'<div style="color:#8B949E; font-size:0.7rem; text-transform:uppercase; '
            f'letter-spacing:0.5px; margin-bottom:6px;">📍 Critical Nodes</div>'
            f'<div style="color:#C9D1D9; font-size:1.3rem; font-weight:700;">{cn_text}</div>'
            f'<div style="color:#8B949E; font-size:0.75rem; margin-top:2px;">most depended-on companies</div>'
            f'<div style="color:#8B949E; font-size:0.72rem; margin-top:6px;">'
            f'Bottlenecks — problems here cascade across the ecosystem'
            f'</div>'
            f'</div>',
            unsafe_allow_html=True,
        )


# ---------------------------------------------------------------------------
# Investment insight feed
# ---------------------------------------------------------------------------

def _render_insight_feed(insights: list[dict]):
    """Render auto-generated investment insight cards above the tabs.

    Cards are grouped by category and sorted by priority.
    """
    category_config = {
        "risk": {"label": "⚠️ RISK", "border": "#FF1744"},
        "opportunity": {"label": "💡 OPPORTUNITY", "border": "#FFD600"},
        "positioning": {"label": "📊 POSITIONING", "border": "#58A6FF"},
        "dependency": {"label": "🔗 DEPENDENCY", "border": "#C9D1D9"},
        "positive": {"label": "✅ POSITIVE", "border": "#00C853"},
    }

    st.markdown(
        '<p style="color:#8B949E; font-size:0.8rem; margin:18px 0 10px 0; '
        'text-transform:uppercase; letter-spacing:0.5px;">💡 Investment Insights</p>',
        unsafe_allow_html=True,
    )

    # Show top 6 insights by priority, then collapse the rest
    display_count = min(6, len(insights))
    for ins in insights[:display_count]:
        cfg = category_config.get(ins["category"], category_config["dependency"])
        priority_label = {1: "CRITICAL", 2: "NOTABLE", 3: "INFO"}.get(ins["priority"], "")
        st.markdown(
            f'<div style="background:#161B22; border-left:4px solid {cfg["border"]}; '
            f'border-top:1px solid #30363D; border-right:1px solid #30363D; '
            f'border-bottom:1px solid #30363D; border-radius:8px; '
            f'padding:12px 16px; margin:6px 0;">'
            f'<div style="display:flex; align-items:center; gap:8px; margin-bottom:4px;">'
            f'<span style="color:{cfg["border"]}; font-size:0.7rem; font-weight:700; '
            f'text-transform:uppercase; letter-spacing:0.5px;">{cfg["label"]}</span>'
            f'<span style="color:#484F58; font-size:0.65rem;">· {priority_label}</span>'
            f'</div>'
            f'<div style="color:#C9D1D9; font-size:0.9rem; font-weight:600; '
            f'margin-bottom:4px;">{ins["headline"]}</div>'
            f'<div style="color:#8B949E; font-size:0.78rem; line-height:1.45;">'
            f'{ins["detail"]}</div>'
            f'<div style="color:#58A6FF; font-size:0.72rem; margin-top:6px; '
            f'font-style:italic;">→ {ins["action"]}</div>'
            f'</div>',
            unsafe_allow_html=True,
        )

    if len(insights) > display_count:
        with st.expander(f"Show {len(insights) - display_count} more insights"):
            for ins in insights[display_count:]:
                cfg = category_config.get(ins["category"], category_config["dependency"])
                st.markdown(
                    f'<div style="background:#161B22; border-left:4px solid {cfg["border"]}; '
                    f'border-top:1px solid #30363D; border-right:1px solid #30363D; '
                    f'border-bottom:1px solid #30363D; border-radius:8px; '
                    f'padding:10px 14px; margin:4px 0;">'
                    f'<span style="color:{cfg["border"]}; font-size:0.65rem; font-weight:700;">'
                    f'{cfg["label"]}</span> '
                    f'<span style="color:#C9D1D9; font-size:0.85rem; font-weight:600;">'
                    f'{ins["headline"]}</span>'
                    f'<div style="color:#8B949E; font-size:0.75rem; margin-top:2px;">'
                    f'{ins["detail"]}</div>'
                    f'</div>',
                    unsafe_allow_html=True,
                )


# ---------------------------------------------------------------------------
# Relationship table
# ---------------------------------------------------------------------------

def _render_relationship_table(relationships: list[dict], metrics_data: dict):
    """Render each relationship as a dark-themed card with health badges."""
    for rel in relationships:
        source = rel["source"]
        target = rel["target"]
        rtype = rel.get("type", "partner")
        desc = rel.get("description", "")
        strength = rel.get("strength", "medium")
        emoji = TYPE_EMOJI.get(rtype, "\U0001f517")  # 🔗 fallback
        rtype_color = TYPE_COLORS.get(rtype, "#C9D1D9")

        source_name = (metrics_data.get(source, {}) or {}).get("name", source)
        target_name = (metrics_data.get(target, {}) or {}).get("name", target)

        source_badge = _ticker_health_badge(source, metrics_data)
        target_badge = _ticker_health_badge(target, metrics_data)

        strength_indicator = " ⬆ Strong" if strength == "strong" else " → Med"

        # Direction arrow
        if rtype == "supplier":
            arrow = "supplies →"
        elif rtype == "customer":
            arrow = "buys from →"
        elif rtype == "competitor":
            arrow = "vs"
        elif rtype == "partner":
            arrow = "⇌"
        elif rtype == "investor":
            arrow = "invests in →"
        else:
            arrow = "→"

        st.markdown(
            f'<div style="'
            f"background: #161B22; border: 1px solid #30363D; border-radius: 10px; "
            f"padding: 14px 18px; margin: 6px 0; "
            f'display: flex; align-items: flex-start; gap: 14px;">'
            # Emoji badge
            f'<span style="font-size: 1.4rem; line-height: 1.4;">{emoji}</span>'
            # Content
            f'<div style="flex: 1; min-width: 0;">'
            f'<div style="color: #C9D1D9; font-size: 0.95rem; display:flex; '
            f'align-items:center; flex-wrap:wrap; gap:2px;">'
            f'<strong style="color: #58A6FF;">{source}</strong>{source_badge}'
            f' <span style="color: #8B949E; font-size: 0.78rem;">({source_name})</span>'
            f' <span style="color: #484F58; margin: 0 4px;">{arrow}</span> '
            f'<strong style="color: #58A6FF;">{target}</strong>{target_badge}'
            f' <span style="color: #8B949E; font-size: 0.78rem;">({target_name})</span>'
            f'</div>'
            f'<div style="color: #8B949E; font-size: 0.8rem; margin-top: 3px;">'
            f'<span style="text-transform: capitalize; color: {rtype_color}; '
            f'font-weight: 600;">{rtype}</span>'
            f' <span style="color: #484F58;">·</span> {desc}'
            f' <span style="color: #484F58;">·</span>'
            f' <span style="color: {rtype_color}; font-size:0.72rem;">{strength_indicator}</span>'
            f'</div>'
            f'</div>'
            f'</div>',
            unsafe_allow_html=True,
        )


# ---------------------------------------------------------------------------
# Network graph
# ---------------------------------------------------------------------------

def _render_relationship_graph(relationships: list[dict], metrics_data: dict):
    """Render a Plotly network graph of company relationships.

    Nodes are colored by health (green/yellow/red) and sized by influence
    (how many others depend on them).  Edges vary in width by relationship
    strength and style by type.
    """
    if not relationships:
        return

    from src.scoring.relationships import compute_influence_score

    # Collect unique nodes
    nodes_set: set[str] = set()
    for rel in relationships:
        nodes_set.add(rel["source"])
        nodes_set.add(rel["target"])
    node_list = sorted(nodes_set)
    n_nodes = len(node_list)

    # Circular layout
    positions = {}
    for i, node in enumerate(node_list):
        angle = 2 * math.pi * i / n_nodes
        positions[node] = (math.cos(angle), math.sin(angle))

    # Compute influence for node sizing
    influence_map: dict[str, int] = {}
    max_influence = 1
    for node in node_list:
        inf = compute_influence_score(node, relationships, metrics_data)
        influence_map[node] = inf["dependent_count"]
        if inf["dependent_count"] > max_influence:
            max_influence = inf["dependent_count"]

    # Build one edge trace per relationship (so width & dash can vary)
    edge_traces: list[go.Scatter] = []
    legend_added: set[str] = set()
    for rel in relationships:
        if rel["source"] not in positions or rel["target"] not in positions:
            continue

        x0, y0 = positions[rel["source"]]
        x1, y1 = positions[rel["target"]]
        rtype = rel.get("type", "partner")
        strength = rel.get("strength", "medium")
        desc = rel.get("description", "")

        color = TYPE_COLORS.get(rtype, "#8B949E")
        width = 3.0 if strength == "strong" else 1.5
        dash = EDGE_DASH.get(rtype, "solid")
        show = rtype.capitalize() not in legend_added
        legend_added.add(rtype.capitalize())

        edge_traces.append(go.Scatter(
            x=[x0, x1, None],
            y=[y0, y1, None],
            mode="lines",
            line=dict(width=width, color=color, dash=dash),
            hovertext=f"{rel['source']} {rtype} {rel['target']}<br>{desc}",
            hoverinfo="text",
            showlegend=show,
            name=rtype.capitalize(),
            legendgroup=rtype,
        ))

    # Node trace
    node_x = [positions[n][0] for n in node_list]
    node_y = [positions[n][1] for n in node_list]
    node_colors: list[str] = []
    node_sizes: list[float] = []
    node_texts: list[str] = []

    for node in node_list:
        entry = metrics_data.get(node, {}) or {}
        qh = entry.get("quick_health") or {}
        verdict = qh.get("verdict", "N/A")
        score = qh.get("score")
        color = _health_color(verdict)
        node_colors.append(color)

        # Size by influence (fallback to market cap, min 12px, max 40px)
        dep_count = influence_map.get(node, 0)
        if dep_count > 0:
            size = max(12, min(40, 14 + dep_count * 6))
        else:
            mcap = entry.get("market_cap") or 0
            max_mcap = max(
                (metrics_data.get(n, {}) or {}).get("market_cap") or 0
                for n in node_list
            )
            size = max(12, min(35, (float(mcap) / max_mcap * 23 + 12))) if max_mcap > 0 else 18
        node_sizes.append(size)

        name = entry.get("name", node)
        score_str = f"{score}/10" if score is not None else "N/A"
        mcap_val = entry.get("market_cap")
        if mcap_val and mcap_val > 0:
            if mcap_val >= 1e12:
                mcap_str = f"${mcap_val/1e12:.1f}T"
            elif mcap_val >= 1e9:
                mcap_str = f"${mcap_val/1e9:.1f}B"
            else:
                mcap_str = f"${mcap_val/1e6:.0f}M"
        else:
            mcap_str = "N/A"
        node_texts.append(
            f"<b>{node}</b> | {name}<br>"
            f"Health: {verdict} ({score_str})<br>"
            f"Market Cap: {mcap_str}"
        )

    node_trace = go.Scatter(
        x=node_x, y=node_y,
        mode="markers+text",
        text=node_list,
        textposition="bottom center",
        textfont=dict(size=10, color="#C9D1D9"),
        marker=dict(
            size=node_sizes,
            color=node_colors,
            line=dict(width=2, color="#30363D"),
        ),
        hovertext=node_texts,
        hoverinfo="text",
        showlegend=False,
    )

    # Health color legend (manual annotations)
    health_legend_traces = []
    for verdict, color_label in [("Strong", "#00C853"), ("Moderate", "#FFD600"), ("Weak", "#FF1744")]:
        health_legend_traces.append(go.Scatter(
            x=[None], y=[None],
            mode="markers",
            marker=dict(size=12, color=color_label, line=dict(width=1.5, color="#30363D")),
            name=f"{verdict} health",
            showlegend=True,
            legendgroup="health",
            legendgrouptitle_text="Node Health",
        ))

    # Strength legend
    strength_legend_traces = []
    for lbl, wid in [("Strong", 3.0), ("Medium", 1.5)]:
        strength_legend_traces.append(go.Scatter(
            x=[None], y=[None],
            mode="lines",
            line=dict(width=wid, color="#8B949E"),
            name=lbl,
            showlegend=True,
            legendgroup="strength",
            legendgrouptitle_text="Relationship Strength",
        ))

    fig = go.Figure(
        data=edge_traces + health_legend_traces + strength_legend_traces + [node_trace]
    )
    fig.update_layout(
        title="",
        showlegend=True,
        legend=dict(
            orientation="v",
            yanchor="top",
            y=0.98,
            xanchor="left",
            x=1.01,
            font=dict(color="#8B949E", size=10),
            bgcolor="rgba(0,0,0,0)",
            groupclick="togglegroup",
        ),
        height=550,
        margin=dict(l=20, r=140, t=20, b=20),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        xaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
        yaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
        hovermode="closest",
    )

    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
