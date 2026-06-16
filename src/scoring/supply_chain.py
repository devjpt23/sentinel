"""
Supply chain scoring — two-way exposure, geographic concentration,
revenue-at-risk, and country risk aggregation.

Complements relationships.py (dependency/influence/competitive scoring)
with Bloomberg SPLC-style metrics.
"""

from __future__ import annotations


# ---------------------------------------------------------------------------
# Two-way exposure (the core SPLC insight)
# ---------------------------------------------------------------------------

def compute_two_way_exposure(
    ticker: str,
    enriched: dict,
    direction: str = "company",
) -> dict:
    """Compute the two-way exposure view — who depends on whom.

    COMPANY EXPOSURE mode (direction="company"):
        "To whom is the center company most exposed?"
        Suppliers sorted by % of center company's COGS (desc)
        Customers sorted by % of center company's revenue (desc)

    RELATIONSHIP EXPOSURE mode (direction="relationship"):
        "Who is most exposed to the center company?"
        Suppliers sorted by % of THEIR revenue from center company (desc)
        Customers sorted by % of THEIR COGS paid to center company (desc)

    Args:
        ticker: the center company ticker
        enriched: result of get_enriched_relationships(ticker)
        direction: "company" or "relationship"

    Returns dict with suppliers and customers lists, each enriched with
    exposure_pct, exposure_label, and sort_rank.
    """
    ticker_u = ticker.upper()

    def _sort_suppliers(rels: list[dict]) -> list[dict]:
        result = []
        for r in rels:
            fin = r.get("financials") or {}
            if direction == "company":
                exposure_pct = fin.get("cogs_pct")
            else:
                exposure_pct = fin.get("supplier_revenue_pct")
            if exposure_pct is not None:
                label = (
                    f"{exposure_pct}% of {ticker_u} COGS"
                    if direction == "company" else
                    f"{exposure_pct}% of supplier revenue from {ticker_u}"
                )
            else:
                label = "N/A — financial data not available"
            result.append({**r, "exposure_pct": exposure_pct, "exposure_label": label})
        result.sort(key=lambda x: -(x.get("exposure_pct") or 0))
        for i, r in enumerate(result):
            r["sort_rank"] = i + 1
        return result

    def _sort_customers(rels: list[dict]) -> list[dict]:
        result = []
        for r in rels:
            fin = r.get("financials") or {}
            if direction == "company":
                exposure_pct = fin.get("revenue_pct")
            else:
                exposure_pct = fin.get("customer_cogs_pct")
            if exposure_pct is not None:
                label = (
                    f"{exposure_pct}% of {ticker_u} revenue"
                    if direction == "company" else
                    f"{exposure_pct}% of customer COGS to {ticker_u}"
                )
            else:
                label = "N/A — financial data not available"
            result.append({**r, "exposure_pct": exposure_pct, "exposure_label": label})
        result.sort(key=lambda x: -(x.get("exposure_pct") or 0))
        for i, r in enumerate(result):
            r["sort_rank"] = i + 1
        return result

    suppliers = _sort_suppliers(enriched.get("suppliers", []))
    customers = _sort_customers(enriched.get("customers", []))
    competitors = enriched.get("competitors", [])
    partners = enriched.get("partners", [])

    # Find asymmetric dependencies (classic SPLC insight)
    asymmetric: list[dict] = []
    for s in suppliers:
        fin = s.get("financials") or {}
        cogs = fin.get("cogs_pct", 0)
        rev = fin.get("supplier_revenue_pct", 0)
        if rev > 30 and cogs < 10:
            asymmetric.append({
                "ticker": s["target"],
                "type": "supplier",
                "asymmetry": f"{s['target']} gets {rev}% of revenue from {ticker_u} but is only {cogs}% of {ticker_u}'s COGS",
                "verdict": "Supplier is far more dependent on center than vice versa",
            })
    for c in customers:
        fin = c.get("financials") or {}
        rev = fin.get("revenue_pct", 0)
        cogs = fin.get("customer_cogs_pct", 0)
        if rev > 30 and cogs < 10:
            asymmetric.append({
                "ticker": c["target"],
                "type": "customer",
                "asymmetry": f"{c['target']} pays {cogs}% of COGS to {ticker_u} but is only {rev}% of {ticker_u}'s revenue",
                "verdict": "Customer is far more dependent on center than vice versa",
            })

    return {
        "direction": direction,
        "direction_label": "Company Exposure" if direction == "company" else "Relationship Exposure",
        "suppliers": suppliers,
        "customers": customers,
        "competitors": competitors,
        "partners": partners,
        "asymmetric_dependencies": asymmetric,
    }


# ---------------------------------------------------------------------------
# Geographic concentration
# ---------------------------------------------------------------------------

def compute_geographic_concentration(geo_breakdown: list[dict]) -> dict:
    """Calculate Herfindahl-Hirschman Index for geographic concentration.

    HHI: sum of squared market shares (0-10000).  >2500 = highly concentrated.
    """
    total = sum(g["total_relationships"] for g in geo_breakdown)
    if total == 0:
        return {
            "hhi_score": 0,
            "hhi_verdict": "No Data",
            "diversification_verdict": "No Data",
            "country_count": 0,
            "dominant_region": None,
        }

    hhi = sum((g["total_relationships"] / total * 100) ** 2 for g in geo_breakdown)
    hhi = round(hhi, 1)

    if hhi > 2500:
        hhi_verdict = "Highly Concentrated"
        div_verdict = "Concentrated"
    elif hhi > 1500:
        hhi_verdict = "Moderately Concentrated"
        div_verdict = "Moderate"
    else:
        hhi_verdict = "Diversified"
        div_verdict = "Diversified"

    # Dominant region
    region_counts: dict[str, int] = {}
    for g in geo_breakdown:
        region = _get_region(g["country_code"])
        region_counts[region] = region_counts.get(region, 0) + g["total_relationships"]
    dominant_region = max(region_counts, key=lambda k: region_counts[k]) if region_counts else None

    return {
        "hhi_score": hhi,
        "hhi_verdict": hhi_verdict,
        "diversification_verdict": div_verdict,
        "country_count": len(geo_breakdown),
        "dominant_region": dominant_region,
        "country_breakdown": geo_breakdown,
    }


def _get_region(country_code: str) -> str:
    """Map ISO country code to region."""
    regions = {
        "US": "North America", "MX": "North America",
        "TW": "Asia", "KR": "Asia", "CN": "Asia", "JP": "Asia",
        "SG": "Asia", "MY": "Asia", "IN": "Asia", "VN": "Asia",
        "NL": "Europe", "DE": "Europe", "GB": "Europe", "IE": "Europe", "DK": "Europe",
        "IL": "Middle East",
        "CL": "South America",
        "AU": "Oceania",
    }
    return regions.get(country_code.upper(), "Other")


# ---------------------------------------------------------------------------
# Country risk scoring
# ---------------------------------------------------------------------------

def compute_country_risk_score(geo_breakdown: list[dict]) -> dict:
    """Aggregate country risk across supply chain relationships.

    Returns weighted risk score (0-100), sanctions exposure, and breakdown.
    """
    if not geo_breakdown:
        return {
            "weighted_risk_score": None,
            "risk_verdict": "No Data",
            "sanctions_exposure": False,
            "sanctions_countries": [],
            "highest_risk_country": None,
        }

    total = sum(g["total_relationships"] for g in geo_breakdown)
    if total == 0:
        return {"weighted_risk_score": None, "risk_verdict": "No Data", "sanctions_exposure": False}

    weighted = 0.0
    sanctions_countries = []
    highest_risk = None
    highest_risk_score = 0

    for g in geo_breakdown:
        risk = g.get("risk_score") or 0
        weight = g["total_relationships"] / total
        weighted += risk * weight

        if g.get("sanctions_flag"):
            sanctions_countries.append(g["country_name"])

        if risk > highest_risk_score:
            highest_risk_score = risk
            highest_risk = g

    if weighted < 20:
        verdict = "Low Supply Chain Risk"
    elif weighted < 40:
        verdict = "Moderate Supply Chain Risk"
    elif weighted < 60:
        verdict = "Elevated Supply Chain Risk"
    else:
        verdict = "High Supply Chain Risk"

    return {
        "weighted_risk_score": round(weighted, 1),
        "risk_verdict": verdict,
        "sanctions_exposure": len(sanctions_countries) > 0,
        "sanctions_countries": sanctions_countries,
        "highest_risk_country": highest_risk,
        "risk_breakdown": [
            {"country": g["country_name"], "risk_score": g.get("risk_score"),
             "weight_pct": round(g["total_relationships"] / total * 100, 1)}
            for g in sorted(geo_breakdown, key=lambda x: -(x.get("risk_score") or 0))[:5]
        ],
    }


# ---------------------------------------------------------------------------
# Revenue at risk (tariff scenario analysis)
# ---------------------------------------------------------------------------

def compute_revenue_at_risk(
    ticker: str,
    enriched: dict,
    geo_breakdown: list[dict],
    tariff_scenario_pct: float = 25.0,
) -> dict:
    """Estimate revenue at risk under a tariff scenario.

    Looks at customer relationships in high-tariff-exposure countries.
    """
    customers = enriched.get("customers", [])
    if not customers:
        return {"revenue_at_risk_pct": 0, "revenue_at_risk_verdict": "No customer data"}

    # Find high-tariff-exposure countries
    high_tariff_countries = {
        g["country_code"] for g in geo_breakdown
        if g.get("tariff_exposure") == "high" or g.get("sanctions_flag")
    }

    at_risk_pct = 0.0
    affected = []
    for c in customers:
        geo = c.get("target_geo") or {}
        domicile = geo.get("domicile", "??")
        if domicile in high_tariff_countries or any(m in high_tariff_countries for m in geo.get("manufacturing", [])):
            fin = c.get("financials") or {}
            pct = fin.get("revenue_pct", 0)
            at_risk_pct += pct
            affected.append({
                "ticker": c["target"],
                "country": domicile,
                "revenue_pct": pct,
            })

    # Scenario impact
    scenario_impact = at_risk_pct * (tariff_scenario_pct / 100)

    if at_risk_pct > 20:
        verdict = "High — significant tariff vulnerability"
    elif at_risk_pct > 10:
        verdict = "Moderate — monitor trade policy"
    elif at_risk_pct > 0:
        verdict = "Low — limited tariff exposure"
    else:
        verdict = "Minimal — no material tariff exposure identified"

    return {
        "revenue_at_risk_pct": round(at_risk_pct, 1),
        "scenario_impact_pct": round(scenario_impact, 2),
        "scenario_description": (
            f"Under a {tariff_scenario_pct:.0f}% tariff on high-risk countries, "
            f"approximately {scenario_impact:.1f}% of {ticker.upper()}'s revenue "
            f"could be affected through customer relationships."
        ),
        "verdict": verdict,
        "affected_customers": affected,
    }
