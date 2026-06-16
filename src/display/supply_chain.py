"""
Supply Chain display — Bloomberg SPLC-style hub-and-spoke visualization,
geographic breakdown with interactive map, exposure table, and risk overlay.

Four tabs:
  1. Hub & Spoke  — directed network graph with two-way exposure toggle
  2. Geographic   — interactive world map with factory locations
  3. Exposure Table — sortable financial quantification table
  4. Risk          — country risk, sanctions, tariff exposure
"""

from __future__ import annotations

import streamlit as st
import plotly.graph_objects as go

from src.data.supply_chain_data import (
    get_enriched_relationships,
    get_geo_breakdown,
    compute_exposure_summary,
)
from src.scoring.supply_chain import (
    compute_two_way_exposure,
    compute_geographic_concentration,
    compute_country_risk_score,
    compute_revenue_at_risk,
)

# ---------------------------------------------------------------------------
# Colors & helpers — reuse same palette as company_linkage.py
# ---------------------------------------------------------------------------

TYPE_COLORS = {
    "supplier": "#FFD600",
    "customer": "#58A6FF",
    "competitor": "#FF6B7A",
    "partner": "#00C853",
}

TYPE_EMOJI = {
    "supplier": "⬆️",
    "customer": "⬇️",
    "competitor": "⚔️",
    "partner": "\U0001f91d",
}

EDGE_DASH = {
    "supplier": "solid",
    "customer": "solid",
    "competitor": "dash",
    "partner": "dot",
}

RISK_COLORS = {
    "Low": "#00C853",
    "Moderate": "#FFD600",
    "Elevated": "#FF9800",
    "High": "#FF1744",
}


def _health_badge(verdict: str, score: int | None = None) -> str:
    """HTML snippet for a health verdict badge."""
    color = {"Strong": "#00C853", "Moderate": "#FFD600", "Weak": "#FF1744"}.get(verdict, "#8B949E")
    bg = {"Strong": "#00C85322", "Moderate": "#FFD60022", "Weak": "#FF174422"}.get(verdict, "#8B949E22")
    score_text = f" {score}/10" if score is not None else ""
    return (
        f'<span style="background:{bg}; color:{color}; font-size:0.68rem; '
        f'font-weight:600; padding:1px 7px; border-radius:8px; margin-left:6px; '
        f'white-space:nowrap;">{verdict}{score_text}</span>'
    )


def _resolve_name(ticker: str, rel: dict | None, metrics_data: dict) -> str:
    """Resolve a company display name from multiple sources.

    Priority: yfinance metrics_data > curated target_name > ticker fallback
    """
    # Try yfinance first
    entry = metrics_data.get(ticker.upper(), {}) or {}
    name = entry.get("name")
    if name and name != ticker:
        return name
    # Try curated JSON's target_name field
    if rel and rel.get("target_name"):
        return rel["target_name"]
    return ticker


def _card(inner_html: str) -> str:
    """Wrap content in a dark-themed card."""
    return (
        f'<div style="background:#161B22; border:1px solid #30363D; '
        f'border-radius:10px; padding:14px 16px; height:100%;">{inner_html}</div>'
    )


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def render_supply_chain_tab(ticker: str, metrics_data: dict):
    """Render the Supply Chain section for a single ticker.

    Called from app.py after Red Flags, before Deep Dive.
    """
    # Load data
    enriched = get_enriched_relationships(ticker)
    geo_breakdown = get_geo_breakdown(ticker)
    summary = compute_exposure_summary(ticker)

    total_rels = (
        summary["total_suppliers"] + summary["total_customers"] +
        summary["total_competitors"] + summary["total_partners"]
    )

    if total_rels == 0:
        st.markdown(
            '<div style="color:#8B949E; font-size:0.9rem; padding:30px 20px; '
            'text-align:center; background:#161B22; border:1px solid #30363D; '
            'border-radius:12px;">'
            "No supply chain relationships mapped for this ticker yet.<br>"
            '<span style="font-size:0.8rem;">Relationships are sourced from SEC filings '
            "and curated data — check back as we add more.</span>"
            "</div>",
            unsafe_allow_html=True,
        )
        return

    # ── Summary cards ──
    _render_summary_cards(ticker, summary, enriched, geo_breakdown)

    # ── Tabs ──
    tab1, tab2, tab3, tab4 = st.tabs([
        "\U0001f578️ Hub & Spoke",
        "\U0001f5fa️ Geographic",
        "\U0001f4cb Exposure Table",
        "⚠️ Risk",
    ])

    with tab1:
        _render_hub_and_spoke(ticker, enriched, metrics_data)

    with tab2:
        _render_geographic(ticker, geo_breakdown)

    with tab3:
        _render_exposure_table(ticker, enriched, metrics_data)

    with tab4:
        _render_risk(ticker, enriched, geo_breakdown)


# ---------------------------------------------------------------------------
# Summary cards
# ---------------------------------------------------------------------------

def _render_summary_cards(ticker: str, summary: dict, enriched: dict, geo_breakdown: list[dict]):
    """Render a row of summary metric cards above the tabs."""

    # Supplier stats
    supplier_known = summary["supplier_cogs_pct"]
    top_sup = summary.get("top_supplier") or {}
    top_sup_ticker = top_sup.get("ticker", "—")
    top_sup_pct = top_sup.get("cogs_pct", 0)

    # Customer stats
    customer_known = summary["customer_revenue_pct"]
    top_cust = summary.get("top_customer") or {}
    top_cust_ticker = top_cust.get("ticker", "—")
    top_cust_pct = top_cust.get("revenue_pct", 0)

    # Critical dependency flag
    crit_flag = summary.get("critical_dependency_flag", False)
    crit_border = "border-left:3px solid #FF1744;" if crit_flag else ""

    # Country stats
    dominant = summary.get("dominant_country") or {}
    riskiest = summary.get("riskiest_country") or {}

    cols = st.columns(4)

    with cols[0]:
        dependency_note = ""
        if crit_flag and summary.get("critical_dependency_detail"):
            dependency_note = (
                f'<div style="color:#FF1744; font-size:0.7rem; margin-top:6px;">'
                f'⚠️ {summary["critical_dependency_detail"]}</div>'
            )
        st.markdown(_card(
            f'<div style="color:#8B949E; font-size:0.7rem; text-transform:uppercase; '
            f'letter-spacing:0.5px; margin-bottom:6px;">⬆️ Suppliers</div>'
            f'<div style="color:#C9D1D9; font-size:1.3rem; font-weight:700;">'
            f'{summary["total_suppliers"]}</div>'
            f'<div style="color:#8B949E; font-size:0.75rem; margin-top:2px;">'
            f'Top: <span style="color:#58A6FF;">{top_sup_ticker}</span> ({top_sup_pct}% COGS)'
            f'</div>'
            f'<div style="color:#8B949E; font-size:0.75rem;">'
            f'{supplier_known}% of COGS quantified</div>'
            f'{dependency_note}'
        ), unsafe_allow_html=True)

    with cols[1]:
        st.markdown(_card(
            f'<div style="color:#8B949E; font-size:0.7rem; text-transform:uppercase; '
            f'letter-spacing:0.5px; margin-bottom:6px;">⬇️ Customers</div>'
            f'<div style="color:#C9D1D9; font-size:1.3rem; font-weight:700;">'
            f'{summary["total_customers"]}</div>'
            f'<div style="color:#8B949E; font-size:0.75rem; margin-top:2px;">'
            f'Top: <span style="color:#58A6FF;">{top_cust_ticker}</span> ({top_cust_pct}% revenue)'
            f'</div>'
            f'<div style="color:#8B949E; font-size:0.75rem;">'
            f'{customer_known}% of revenue quantified</div>'
        ), unsafe_allow_html=True)

    with cols[2]:
        dom_name = dominant.get("country_name", "—")
        dom_code = dominant.get("country_code", "")
        dom_count = dominant.get("total_relationships", 0)
        st.markdown(_card(
            f'<div style="color:#8B949E; font-size:0.7rem; text-transform:uppercase; '
            f'letter-spacing:0.5px; margin-bottom:6px;">\U0001f30d Dominant Country</div>'
            f'<div style="color:#C9D1D9; font-size:1.3rem; font-weight:700;">'
            f'{dom_name} <span style="font-size:0.8rem;color:#8B949E;">{dom_code}</span></div>'
            f'<div style="color:#8B949E; font-size:0.75rem; margin-top:2px;">'
            f'{dom_count} relationship{"s" if dom_count != 1 else ""}</div>'
        ), unsafe_allow_html=True)

    with cols[3]:
        risk_name = riskiest.get("country_name", "—")
        risk_label = riskiest.get("risk_label", "—")
        risk_color = RISK_COLORS.get(risk_label, "#8B949E")
        st.markdown(_card(
            f'<div style="color:#8B949E; font-size:0.7rem; text-transform:uppercase; '
            f'letter-spacing:0.5px; margin-bottom:6px;">⚠️ Highest Risk Country</div>'
            f'<div style="color:#C9D1D9; font-size:1.3rem; font-weight:700;">'
            f'{risk_name}</div>'
            f'<div style="color:{risk_color}; font-size:0.75rem; margin-top:2px; font-weight:600;">'
            f'{risk_label} Risk</div>'
        ), unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Tab 1: Hub & Spoke graph
# ---------------------------------------------------------------------------

def _render_hub_and_spoke(ticker: str, enriched: dict, metrics_data: dict):
    """Render the Bloomberg-style hub-and-spoke directed graph."""
    # Two-way exposure toggle
    direction = st.radio(
        "Sort By",
        ["Company Exposure", "Relationship Exposure"],
        horizontal=True,
        help=(
            "**Company Exposure**: Who does **{0}** depend on most?\n\n"
            "**Relationship Exposure**: Who depends most on **{0}**?"
        ).format(ticker.upper()),
        label_visibility="collapsed",
    )
    direction_key = "company" if direction == "Company Exposure" else "relationship"

    exposure = compute_two_way_exposure(ticker, enriched, direction_key)

    suppliers = exposure["suppliers"]
    customers = exposure["customers"]
    competitors = exposure["competitors"]
    partners = exposure["partners"]

    # Build hub-and-spoke positions
    # Center = (0, 0) — the analyzed ticker
    # Suppliers on left (x negative), Customers on right (x positive)
    # Competitors above, Partners below

    center_x, center_y = 0.0, 0.0
    nodes: dict[str, dict] = {}  # ticker -> {x, y, size, color, text, type}

    def _spread_positions(count: int, side: str) -> list[tuple[float, float]]:
        """Generate y-spread positions for a side."""
        if count == 0:
            return []
        if side == "left":
            x = -1.2
        elif side == "right":
            x = 1.2
        elif side == "top":
            x = 0.0
        else:
            x = 0.0

        positions = []
        if count == 1:
            y = 0.0 if side == "top" else (0.5 if side == "bottom" else 0.0)
            if side == "top":
                y = 1.0
            elif side == "bottom":
                y = -1.0
            positions.append((x, y))
        else:
            if side == "top":
                span = min(1.5, count * 0.35)
                for i in range(count):
                    y = 0.5 + (i - (count - 1) / 2) * (span / max(1, count - 1))
                    x_off = (i - (count - 1) / 2) * 0.2
                    positions.append((x_off, y))
            elif side == "bottom":
                span = min(1.5, count * 0.35)
                for i in range(count):
                    y = -0.5 - (i - (count - 1) / 2) * (span / max(1, count - 1))
                    x_off = (i - (count - 1) / 2) * 0.2
                    positions.append((x_off, y))
            elif side == "left":
                span = min(2.5, count * 0.35)
                for i in range(count):
                    y = (i - (count - 1) / 2) * (span / max(1, count - 1))
                    positions.append((x, y))
            else:  # right
                span = min(2.5, count * 0.35)
                for i in range(count):
                    y = (i - (count - 1) / 2) * (span / max(1, count - 1))
                    positions.append((x, y))
        return positions

    # Generate positions
    sup_pos = _spread_positions(len(suppliers), "left")
    cust_pos = _spread_positions(len(customers), "right")
    comp_pos = _spread_positions(len(competitors), "top")
    part_pos = _spread_positions(len(partners), "bottom")

    # Add center node
    nodes[ticker.upper()] = {
        "x": center_x, "y": center_y, "size": 30,
        "color": "#FFFFFF", "type": "center",
        "name": _resolve_name(ticker.upper(), None, metrics_data),
    }

    # Add supplier nodes
    for i, s in enumerate(suppliers):
        t = s.get("other", s["target"])
        exp = s.get("exposure_pct")
        node_size = 18 if exp is None else max(10, min(28, 12 + exp * 0.4))
        nodes[t] = {
            "x": sup_pos[i][0], "y": sup_pos[i][1],
            "size": node_size,
            "color": TYPE_COLORS["supplier"], "type": "supplier",
            "name": _resolve_name(t, None, metrics_data),
            "exposure_pct": exp,
            "exposure_label": s.get("exposure_label", ""),
        }

    # Add customer nodes
    for i, c in enumerate(customers):
        t = c.get("other", c["target"])
        exp = c.get("exposure_pct")
        node_size = 18 if exp is None else max(10, min(28, 12 + exp * 0.4))
        nodes[t] = {
            "x": cust_pos[i][0], "y": cust_pos[i][1],
            "size": node_size,
            "color": TYPE_COLORS["customer"], "type": "customer",
            "name": _resolve_name(t, None, metrics_data),
            "exposure_pct": exp,
            "exposure_label": c.get("exposure_label", ""),
        }

    # Add competitor nodes
    for i, comp in enumerate(competitors):
        t = comp.get("other", comp["target"])
        nodes[t] = {
            "x": comp_pos[i][0], "y": comp_pos[i][1],
            "size": 14,
            "color": TYPE_COLORS["competitor"], "type": "competitor",
            "name": _resolve_name(t, None, metrics_data),
        }

    # Add partner nodes
    for i, p in enumerate(partners):
        t = p.get("other", p["target"])
        nodes[t] = {
            "x": part_pos[i][0], "y": part_pos[i][1],
            "size": 12,
            "color": TYPE_COLORS["partner"], "type": "partner",
            "name": _resolve_name(t, None, metrics_data),
        }

    # Build edge traces
    edge_traces = []
    legend_added: set[str] = set()

    def _add_edges(rel_list: list[dict], from_center: bool = True):
        for rel in rel_list:
            s = ticker.upper() if from_center else rel.get("other", rel["source"])
            t = rel.get("other", rel["target"]) if from_center else ticker.upper()
            if s not in nodes or t not in nodes:
                continue

            rtype = rel.get("type", "partner")
            strength = rel.get("strength", "medium")
            fin = rel.get("financials") or {}
            color = TYPE_COLORS.get(rtype, "#8B949E")
            width = 3.0 if strength == "strong" else 1.5
            dash = EDGE_DASH.get(rtype, "solid")

            # Edge label (financial %)
            edge_label = ""
            if rtype == "supplier":
                pct = fin.get("cogs_pct") or rel.get("exposure_pct", 0)
                if pct:
                    edge_label = f"{pct}%"
            elif rtype == "customer":
                pct = fin.get("revenue_pct") or rel.get("exposure_pct", 0)
                if pct:
                    edge_label = f"{pct}%"

            show = rtype.capitalize() not in legend_added
            legend_added.add(rtype.capitalize())

            edge_traces.append(go.Scatter(
                x=[nodes[s]["x"], nodes[t]["x"], None],
                y=[nodes[s]["y"], nodes[t]["y"], None],
                mode="lines" + ("+text" if edge_label else ""),
                line=dict(width=width, color=color, dash=dash),
                text=[None, edge_label, None] if edge_label else None,
                textposition="middle center",
                textfont=dict(size=9, color=color),
                hovertext=f"{s} {rtype} {t}<br>{rel.get('description', '')}",
                hoverinfo="text",
                showlegend=show,
                name=rtype.capitalize(),
                legendgroup=rtype,
            ))

    _add_edges(suppliers)
    _add_edges(customers)
    _add_edges(competitors)
    _add_edges(partners)

    # Node trace
    node_x = [n["x"] for n in nodes.values()]
    node_y = [n["y"] for n in nodes.values()]
    node_sizes = [n["size"] for n in nodes.values()]
    node_colors = [n["color"] for n in nodes.values()]
    node_labels = list(nodes.keys())
    node_texts = []
    for tick, n in nodes.items():
        txt = f"<b>{tick}</b> | {n['name']}"
        if n.get("exposure_label"):
            txt += f"<br>{n['exposure_label']}"
        node_texts.append(txt)

    # Center node has bold label
    node_textpositions = ["middle center" if t == ticker.upper() else "middle right" for t in nodes]

    node_trace = go.Scatter(
        x=node_x, y=node_y,
        mode="markers+text",
        text=node_labels,
        textposition=node_textpositions,
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

    # Health legend
    health_legend = []
    for verdict, color in [("Strong", "#00C853"), ("Moderate", "#FFD600"), ("Weak", "#FF1744")]:
        health_legend.append(go.Scatter(
            x=[None], y=[None], mode="markers",
            marker=dict(size=12, color=color, line=dict(width=1.5, color="#30363D")),
            name=f"{verdict} health",
            showlegend=True, legendgroup="health",
            legendgrouptitle_text="Node Health",
        ))

    fig = go.Figure(data=edge_traces + health_legend + [node_trace])
    fig.update_layout(
        showlegend=True,
        legend=dict(
            orientation="v", yanchor="top", y=0.98, xanchor="left", x=1.01,
            font=dict(color="#8B949E", size=10), bgcolor="rgba(0,0,0,0)",
            groupclick="togglegroup",
        ),
        height=500,
        margin=dict(l=20, r=140, t=20, b=20),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        xaxis=dict(showgrid=False, zeroline=False, showticklabels=False, range=[-2, 2]),
        yaxis=dict(showgrid=False, zeroline=False, showticklabels=False, range=[-2, 2]),
        hovermode="closest",
    )

    # Add direction labels
    fig.add_annotation(x=-1.2, y=1.5, text="<b>SUPPLIERS</b>", showarrow=False,
                        font=dict(size=10, color="#FFD600"))
    fig.add_annotation(x=1.2, y=1.5, text="<b>CUSTOMERS</b>", showarrow=False,
                        font=dict(size=10, color="#58A6FF"))
    if competitors:
        fig.add_annotation(x=0, y=1.8, text="<b>COMPETITORS</b>", showarrow=False,
                            font=dict(size=10, color="#FF6B7A"))

    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})

    # Asymmetric dependency callout
    asym = exposure.get("asymmetric_dependencies", [])
    if asym:
        st.markdown(
            '<p style="color:#FFD600; font-size:0.8rem; margin-top:10px;">'
            '⚠️ <b>Asymmetric Dependencies Found:</b></p>',
            unsafe_allow_html=True,
        )
        for a in asym[:3]:
            st.markdown(
                f'<div style="color:#8B949E; font-size:0.78rem; margin:4px 0 4px 12px;">'
                f'• {a["asymmetry"]}</div>',
                unsafe_allow_html=True,
            )


# ---------------------------------------------------------------------------
# Tab 2: Geographic map
# ---------------------------------------------------------------------------

def _render_geographic(ticker: str, geo_breakdown: list[dict]):
    """Render the geographic breakdown with choropleth map + country table."""
    if not geo_breakdown:
        st.markdown(
            '<div style="color:#8B949E; font-size:0.85rem; padding:20px;">'
            'No geographic data available for this supply chain.</div>',
            unsafe_allow_html=True,
        )
        return

    geo_concentration = compute_geographic_concentration(geo_breakdown)

    # Concentration stats
    cols = st.columns(4)
    with cols[0]:
        st.metric("Countries in Chain", geo_concentration["country_count"])
    with cols[1]:
        st.metric("HHI Score", geo_concentration["hhi_score"], help="Herfindahl-Hirschman Index — >2500 = concentrated")
    with cols[2]:
        st.metric("Diversification", geo_concentration["diversification_verdict"])
    with cols[3]:
        st.metric("Dominant Region", geo_concentration.get("dominant_region") or "N/A")

    st.markdown("<br>", unsafe_allow_html=True)

    # Build choropleth
    iso_codes = []
    exposure_values = []
    hover_texts = []
    for g in geo_breakdown:
        # Convert 2-letter to 3-letter ISO where possible for choropleth
        iso3 = _iso2_to_iso3(g["country_code"])
        if iso3:
            iso_codes.append(iso3)
            total = g.get("total_relationships", 0)
            exposure_values.append(total)
            sanctions = "⚠️ SANCTIONS" if g.get("sanctions_flag") else ""
            risk = g.get("risk_label", "")
            hover_texts.append(
                f"<b>{g['country_name']}</b><br>"
                f"Suppliers: {g.get('supplier_count', 0)} | "
                f"Customers: {g.get('customer_count', 0)}<br>"
                f"Total relationships: {total}<br>"
                f"Risk: {risk} | {sanctions}"
            )

    if iso_codes:
        max_val = max(exposure_values) if exposure_values else 1
        zmin_val = 0
        zmax_val = max(5, max_val)  # cap scale so countries with 1-2 rels still visible
        choropleth = go.Choropleth(
            locations=iso_codes,
            z=exposure_values,
            text=hover_texts,
            zmin=zmin_val, zmax=zmax_val,
            colorscale=[
                [0, "#161B22"],
                [0.2, "#1A3A5C"],
                [0.4, "#3A6B8C"],
                [0.6, "#FFD600"],
                [0.8, "#FF9800"],
                [1.0, "#FF1744"],
            ],
            colorbar=dict(
                title=dict(text="Relationships", font=dict(color="#8B949E", size=10)),
                tickfont=dict(color="#8B949E", size=9),
                thickness=10, len=0.5,
            ),
            hoverinfo="text",
            showscale=True,
            marker_line=dict(width=0.5, color="#30363D"),
        )

        fig = go.Figure(data=[choropleth])
        fig.update_geos(
            projection_type="natural earth",
            showcoastlines=True, coastlinecolor="#30363D",
            showland=True, landcolor="#0D1117",
            showocean=True, oceancolor="#0D1117",
            showcountries=True, countrycolor="#21262D",
            showframe=False,
        )
        fig.update_layout(
            height=400,
            margin=dict(l=0, r=0, t=0, b=10),
            paper_bgcolor="rgba(0,0,0,0)",
            geo=dict(bgcolor="rgba(0,0,0,0)"),
            dragmode=False,
        )
        st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})

    # Country breakdown — expandable cards with company lists
    st.markdown(
        '<p style="color:#8B949E; font-size:0.8rem; margin-top:16px; '
        'text-transform:uppercase; letter-spacing:0.5px;">Country Breakdown</p>',
        unsafe_allow_html=True,
    )

    for g in geo_breakdown:
        risk_label = g.get("risk_label", "Unknown")
        risk_color = RISK_COLORS.get(risk_label, "#8B949E")
        sanctions_flag = " 🚫 SANCTIONS" if g.get("sanctions_flag") else ""
        geo_risk = g.get("geo_political_risk", "")
        companies = g.get("companies", [])
        sup_count = g.get("supplier_count", 0)
        cust_count = g.get("customer_count", 0)
        comp_count = g.get("competitor_count", 0)
        part_count = g.get("partner_count", 0)
        mfg = " 🏭 Manufacturing presence" if g.get("manufacturing_presence") else ""
        risk_score = g.get("risk_score")
        score_text = f"Risk: {risk_score}/100" if risk_score is not None else ""

        # Build company list with type emojis
        company_str = " · ".join(companies) if companies else ""

        with st.expander(
            f"{g['country_name']} — "
            f"⬆️{sup_count} ⬇️{cust_count} ⚔️{comp_count} 🤝{part_count} | "
            f"{risk_label}{sanctions_flag} {score_text}"
        ):
            st.markdown(
                f'<div style="color:#8B949E; font-size:0.78rem; margin-bottom:6px;">'
                f'{geo_risk}{mfg}</div>',
                unsafe_allow_html=True,
            )
            if company_str:
                st.markdown(
                    f'<div style="color:#C9D1D9; font-size:0.82rem; '
                    f'background:#161B22; border:1px solid #30363D; border-radius:6px; '
                    f'padding:8px 12px; font-family:monospace;">{company_str}</div>',
                    unsafe_allow_html=True,
                )
            else:
                st.markdown(
                    f'<div style="color:#484F58; font-size:0.78rem;">'
                    f'Manufacturing/secondary presence — no direct relationships domiciled here.</div>',
                    unsafe_allow_html=True,
                )


def _iso2_to_iso3(code: str) -> str | None:
    """Convert ISO 3166-1 alpha-2 to alpha-3."""
    mapping = {
        "US": "USA", "CN": "CHN", "TW": "TWN", "KR": "KOR", "JP": "JPN",
        "NL": "NLD", "DE": "DEU", "GB": "GBR", "IE": "IRL", "SG": "SGP",
        "MY": "MYS", "IN": "IND", "VN": "VNM", "IL": "ISR", "MX": "MEX",
        "DK": "DNK", "CL": "CHL", "AU": "AUS", "FR": "FRA", "CA": "CAN",
        "CH": "CHE", "SE": "SWE", "IT": "ITA", "ES": "ESP", "BR": "BRA",
    }
    return mapping.get(code.upper())


# ---------------------------------------------------------------------------
# Tab 3: Exposure table
# ---------------------------------------------------------------------------

def _render_exposure_table(ticker: str, enriched: dict, metrics_data: dict):
    """Render sortable table of all supply chain relationships with financial data."""
    all_rels = []
    for rtype in ("suppliers", "customers", "competitors", "partners"):
        for rel in enriched.get(rtype, []):
            target = rel.get("other", rel["target"])
            fin = rel.get("financials") or {}
            geo = rel.get("target_geo") or {}
            domicile = geo.get("domicile", "??")

            if rtype == "suppliers":
                exposure = f"{fin.get('cogs_pct', '?')}% COGS"
                inverse = f"{fin.get('supplier_revenue_pct', '?')}% of their revenue"
            elif rtype == "customers":
                exposure = f"{fin.get('revenue_pct', '?')}% revenue"
                inverse = f"{fin.get('customer_cogs_pct', '?')}% of their COGS"
            else:
                exposure = "—"
                inverse = "—"

            all_rels.append({
                "Ticker": target,
                "Name": _resolve_name(target, rel, metrics_data),
                "Type": rtype[:-1].capitalize(),
                "Exposure": exposure,
                "Inverse": inverse,
                "Strength": rel.get("strength", "medium").capitalize(),
                "Country": domicile,
                "Description": rel.get("description", "")[:100],
            })

    if not all_rels:
        st.markdown('<div style="color:#8B949E; padding:20px;">No relationship data.</div>',
                    unsafe_allow_html=True)
        return

    # Color-code each row by type
    for r in all_rels:
        color = TYPE_COLORS.get(r["Type"].lower(), "#8B949E")
        name = r["Name"]
        tick = f'<span style="color:#58A6FF; font-weight:600;">{r["Ticker"]}</span>'
        ttype = f'<span style="color:{color}; font-weight:600;">{TYPE_EMOJI.get(r["Type"].lower(), "")} {r["Type"]}</span>'
        exposure_col = f'<span style="color:#C9D1D9;">{r["Exposure"]}</span>'
        inverse_col = f'<span style="color:#8B949E;">{r["Inverse"]}</span>'
        strength_col = f'<span style="color:#8B949E;">{r["Strength"]}</span>'

        st.markdown(
            f'<div style="background:#161B22; border:1px solid #30363D; border-radius:8px; '
            f'padding:10px 14px; margin:4px 0; display:flex; align-items:center; gap:12px;">'
            f'<div style="flex:2; min-width:120px;">{tick} '
            f'<span style="color:#8B949E; font-size:0.78rem;">{name}</span></div>'
            f'<div style="flex:1; min-width:80px;">{ttype}</div>'
            f'<div style="flex:1; min-width:80px;">{exposure_col} '
            f'<span style="color:#484F58; font-size:0.7rem;">/ {r["Inverse"]}</span></div>'
            f'<div style="flex:1; min-width:60px;">{strength_col}</div>'
            f'<div style="flex:0.5; min-width:40px;">'
            f'<span style="color:#8B949E; font-size:0.78rem;">{r["Country"]}</span></div>'
            f'</div>',
            unsafe_allow_html=True,
        )


# ---------------------------------------------------------------------------
# Tab 4: Risk
# ---------------------------------------------------------------------------

def _render_risk(ticker: str, enriched: dict, geo_breakdown: list[dict]):
    """Render risk analysis tab."""
    risk_data = compute_country_risk_score(geo_breakdown)
    revenue_risk = compute_revenue_at_risk(ticker, enriched, geo_breakdown)

    # Risk summary row
    cols = st.columns(4)

    with cols[0]:
        risk_score = risk_data.get("weighted_risk_score")
        risk_verdict = risk_data.get("risk_verdict", "No Data")
        risk_color = "#FF1744" if (risk_score or 0) > 60 else ("#FF9800" if (risk_score or 0) > 40 else "#00C853")
        score_text = f"{risk_score}/100" if risk_score is not None else "N/A"
        st.markdown(_card(
            f'<div style="color:#8B949E; font-size:0.7rem; text-transform:uppercase; '
            f'letter-spacing:0.5px; margin-bottom:6px;">🌍 Weighted Country Risk</div>'
            f'<div style="color:{risk_color}; font-size:1.5rem; font-weight:700;">{score_text}</div>'
            f'<div style="color:#C9D1D9; font-size:0.8rem; margin-top:4px;">{risk_verdict}</div>'
        ), unsafe_allow_html=True)

    with cols[1]:
        sanctions = risk_data.get("sanctions_countries", [])
        sanctions_text = ", ".join(sanctions) if sanctions else "None"
        sanctions_color = "#FF1744" if sanctions else "#00C853"
        st.markdown(_card(
            f'<div style="color:#8B949E; font-size:0.7rem; text-transform:uppercase; '
            f'letter-spacing:0.5px; margin-bottom:6px;">🚫 Sanctions Exposure</div>'
            f'<div style="color:{sanctions_color}; font-size:1.2rem; font-weight:700;">'
            f'{len(sanctions)} countries</div>'
            f'<div style="color:#8B949E; font-size:0.72rem; margin-top:4px;">{sanctions_text}</div>'
        ), unsafe_allow_html=True)

    with cols[2]:
        rev_risk_pct = revenue_risk.get("revenue_at_risk_pct", 0)
        rev_color = "#FF1744" if rev_risk_pct > 20 else ("#FF9800" if rev_risk_pct > 10 else "#00C853")
        st.markdown(_card(
            f'<div style="color:#8B949E; font-size:0.7rem; text-transform:uppercase; '
            f'letter-spacing:0.5px; margin-bottom:6px;">💸 Revenue at Risk (25% tariff)</div>'
            f'<div style="color:{rev_color}; font-size:1.5rem; font-weight:700;">'
            f'{rev_risk_pct}%</div>'
            f'<div style="color:#C9D1D9; font-size:0.8rem; margin-top:4px;">'
            f'{revenue_risk.get("verdict", "")}</div>'
        ), unsafe_allow_html=True)

    with cols[3]:
        highest = risk_data.get("highest_risk_country") or {}
        high_name = highest.get("country_name", "N/A")
        high_risk = highest.get("risk_label", "")
        high_color = RISK_COLORS.get(high_risk, "#8B949E")
        st.markdown(_card(
            f'<div style="color:#8B949E; font-size:0.7rem; text-transform:uppercase; '
            f'letter-spacing:0.5px; margin-bottom:6px;">📍 Highest Risk Country</div>'
            f'<div style="color:{high_color}; font-size:1.2rem; font-weight:700;">{high_name}</div>'
            f'<div style="color:#8B949E; font-size:0.72rem; margin-top:4px;">{high_risk} Risk</div>'
        ), unsafe_allow_html=True)

    # Risk breakdown table
    st.markdown(
        '<p style="color:#8B949E; font-size:0.8rem; margin-top:20px; '
        'text-transform:uppercase; letter-spacing:0.5px;">Risk Breakdown by Country</p>',
        unsafe_allow_html=True,
    )

    breakdown = risk_data.get("risk_breakdown", [])
    for b in breakdown:
        risk_label = b.get("risk_score")
        if risk_label is not None:
            risk_label = "High" if risk_label > 60 else ("Elevated" if risk_label > 40 else ("Moderate" if risk_label > 20 else "Low"))
        risk_color = RISK_COLORS.get(risk_label, "#8B949E") if risk_label else "#8B949E"
        cols = st.columns([3, 2, 2])
        with cols[0]:
            st.markdown(f'<span style="color:#C9D1D9; font-weight:600;">{b["country"]}</span>',
                        unsafe_allow_html=True)
        with cols[1]:
            st.markdown(f'<span style="color:{risk_color}; font-size:0.85rem;">'
                        f'{risk_label or "N/A"} ({b.get("risk_score", "?")}/100)</span>',
                        unsafe_allow_html=True)
        with cols[2]:
            st.markdown(f'<span style="color:#8B949E; font-size:0.78rem;">'
                        f'{b.get("weight_pct", 0)}% of supply chain</span>',
                        unsafe_allow_html=True)

    # Revenue at risk detail
    affected = revenue_risk.get("affected_customers", [])
    if affected:
        st.markdown(
            '<p style="color:#8B949E; font-size:0.8rem; margin-top:16px; '
            'text-transform:uppercase; letter-spacing:0.5px;">Affected Relationships</p>',
            unsafe_allow_html=True,
        )
        st.markdown(
            f'<div style="color:#8B949E; font-size:0.75rem; margin-bottom:8px;">'
            f'{revenue_risk.get("scenario_description", "")}</div>',
            unsafe_allow_html=True,
        )
        for a in affected:
            st.markdown(
                f'<div style="color:#FF9800; font-size:0.78rem; margin:2px 0 2px 12px;">'
                f'• {a["ticker"]} ({a["country"]}) — {a["revenue_pct"]}% of revenue</div>',
                unsafe_allow_html=True,
            )
