"""
Company linkage display — relationships between companies within a sector.

Renders relationship cards (table view) and an optional Plotly network graph.
Called by sector_search.py to show the "Company Relationships" section.
"""

import math
import streamlit as st
import plotly.graph_objects as go

from src.data.company_links import get_relationships_in_group


# Emoji and color per relationship type
TYPE_EMOJI = {
    "supplier": "⬆️",    # ⬆️
    "customer": "⬇️",    # ⬇️
    "competitor": "⚔️",  # ⚔️
    "partner": "\U0001f91d",       # 🤝
    "investor": "\U0001f4b0",      # 💰
}

TYPE_COLORS = {
    "supplier": "#FFD600",
    "customer": "#58A6FF",
    "competitor": "#FF6B7A",
    "partner": "#00C853",
    "investor": "#C9D1D9",
}


def render_sector_linkage(tickers: list[str], metrics_data: dict):
    """Render the relationship section for companies in a sector.

    Shows a table of known relationships, with an optional network graph tab.
    If no relationships exist in the group, shows a friendly empty state.

    Args:
        tickers: List of ticker symbols currently displayed in the sector view.
        metrics_data: Dict of ticker -> metrics (name, market_cap, quick_health, etc.)
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
        f"Found **{len(relationships)}** known "
        f"relationship{'s' if len(relationships) > 1 else ''} "
        f"between companies in this group."
    )

    # Tab view: Table (default) | Network Graph (optional)
    tab_table, tab_graph = st.tabs([
        "\U0001f4cb Relationship Table",
        "\U0001f578️ Relationship Map",
    ])

    with tab_table:
        _render_relationship_table(relationships, metrics_data)

    with tab_graph:
        _render_relationship_graph(relationships, metrics_data)


def _render_relationship_table(relationships: list[dict], metrics_data: dict):
    """Render each relationship as a dark-themed card with emoji, names, and description."""
    for rel in relationships:
        source = rel["source"]
        target = rel["target"]
        rtype = rel.get("type", "partner")
        desc = rel.get("description", "")
        emoji = TYPE_EMOJI.get(rtype, "\U0001f517")  # 🔗 fallback

        source_name = (metrics_data.get(source, {}) or {}).get("name", source)
        target_name = (metrics_data.get(target, {}) or {}).get("name", target)

        st.markdown(
            f'<div style="'
            f"background: #161B22; border: 1px solid #30363D; border-radius: 10px; "
            f"padding: 14px 18px; margin: 6px 0; "
            f'display: flex; align-items: flex-start; gap: 14px;">'
            # Emoji badge
            f'<span style="font-size: 1.4rem; line-height: 1.4;">{emoji}</span>'
            # Content
            f'<div style="flex: 1; min-width: 0;">'
            f'<div style="color: #C9D1D9; font-size: 0.95rem;">'
            f'<strong style="color: #58A6FF;">{source}</strong>'
            f' <span style="color: #8B949E; font-size: 0.8rem;">({source_name})</span>'
            f' <span style="color: #484F58; margin: 0 4px;">→</span> '
            f'<strong style="color: #58A6FF;">{target}</strong>'
            f' <span style="color: #8B949E; font-size: 0.8rem;">({target_name})</span>'
            f'</div>'
            f'<div style="color: #8B949E; font-size: 0.8rem; margin-top: 3px;">'
            f'<span style="text-transform: capitalize; color: {TYPE_COLORS.get(rtype, "#C9D1D9")}; '
            f'font-weight: 600;">{rtype}</span>'
            f' <span style="color: #484F58;">·</span> {desc}'
            f'</div>'
            f'</div>'
            f'</div>',
            unsafe_allow_html=True,
        )


def _render_relationship_graph(relationships: list[dict], metrics_data: dict):
    """Render a Plotly circular network graph of company relationships.

    Nodes are sized by relative market cap. Edges are colored by relationship type.
    Uses a simple circular layout — no networkx dependency needed.
    """
    if not relationships:
        return

    # Collect unique nodes
    nodes_set = set()
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

    # Market cap for node sizing
    max_mcap = 1.0
    for node in node_list:
        mcap = (metrics_data.get(node, {}) or {}).get("market_cap") or 0
        if mcap and mcap > max_mcap:
            max_mcap = float(mcap)

    # Build edge traces per type (for per-type coloring + legend)
    edge_traces = []
    for rtype in ["supplier", "customer", "competitor", "partner", "investor"]:
        type_rels = [r for r in relationships if r.get("type") == rtype]
        if not type_rels:
            continue

        edge_x = []
        edge_y = []
        for rel in type_rels:
            if rel["source"] not in positions or rel["target"] not in positions:
                continue
            x0, y0 = positions[rel["source"]]
            x1, y1 = positions[rel["target"]]
            # Interleave None values to break lines between edges
            edge_x.extend([x0, x1, None])
            edge_y.extend([y0, y1, None])

        color = TYPE_COLORS.get(rtype, "#8B949E")
        edge_traces.append(go.Scatter(
            x=edge_x, y=edge_y,
            mode="lines",
            line=dict(width=1.5, color=color),
            hoverinfo="none",
            showlegend=True,
            name=rtype.capitalize(),
        ))

    # Node trace
    node_x = [positions[n][0] for n in node_list]
    node_y = [positions[n][1] for n in node_list]
    node_sizes = []
    node_texts = []
    for node in node_list:
        mcap_data = metrics_data.get(node, {}) or {}
        mcap = mcap_data.get("market_cap") or 0
        # Scale node size: 12px min, 35px max
        size = max(12, min(35, (float(mcap) / max_mcap * 23 + 12))) if max_mcap > 0 else 18
        node_sizes.append(size)

        name = mcap_data.get("name", node)
        qh = mcap_data.get("quick_health", {}) or {}
        health = qh.get("verdict", "N/A")
        node_texts.append(f"{node}<br>{name}<br>Health: {health}")

    node_trace = go.Scatter(
        x=node_x, y=node_y,
        mode="markers+text",
        text=node_list,
        textposition="bottom center",
        textfont=dict(size=10, color="#C9D1D9"),
        marker=dict(
            size=node_sizes,
            color="#58A6FF",
            line=dict(width=2, color="#30363D"),
        ),
        hovertext=node_texts,
        hoverinfo="text",
        showlegend=False,
    )

    # Build figure
    fig = go.Figure(data=edge_traces + [node_trace])
    fig.update_layout(
        title="",
        showlegend=True,
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1,
            font=dict(color="#8B949E", size=11),
            bgcolor="rgba(0,0,0,0)",
        ),
        height=520,
        margin=dict(l=20, r=20, t=40, b=20),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        xaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
        yaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
        hovermode="closest",
    )

    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
