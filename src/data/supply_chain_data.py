"""
Loader for enriched supply chain data — financial quantification,
geographic mappings, country risk, and Vala-Fi API integration.

Follows the same lru_cache pattern as company_links.py.

Data sources (merged transparently):
  1. company_links.json (curated — financial + geo enriched)
  2. Vala-Fi API        (free, SEC 10-K extraction — live supplier/customer data)
  3. country_risk.json  (curated — geopolitical risk scores)
  4. yfinance           (already in pipeline — country, sector, market cap)
"""

from __future__ import annotations

import json
import os
import time
from functools import lru_cache
import requests

from src.data.company_links import get_relationships_for_ticker, load_relationships

# ---------------------------------------------------------------------------
# Vala-Fi API client
# ---------------------------------------------------------------------------

VALAFI_API_KEY = "vfi_dev_c55b4ff47b1d5cd33c2d1f03b18021c3"
VALAFI_BASE = "https://api.valafi.dev/v1"
VALAFI_TIMEOUT = 15  # seconds


def _valafi_get(endpoint: str, params: dict | None = None) -> dict | None:
    """Call Vala-Fi API with error handling. Returns parsed JSON or None."""
    url = f"{VALAFI_BASE}{endpoint}"
    headers = {"X-API-Key": VALAFI_API_KEY, "Accept": "application/json"}
    try:
        resp = requests.get(url, headers=headers, params=params or {}, timeout=VALAFI_TIMEOUT)
        if resp.status_code == 200:
            return resp.json()
        elif resp.status_code == 429:
            time.sleep(2)
            resp = requests.get(url, headers=headers, params=params or {}, timeout=VALAFI_TIMEOUT)
            if resp.status_code == 200:
                return resp.json()
        return None
    except Exception:
        return None


# Time-bounded cache for Vala-Fi results (respects 50 req/day limit).
# TTL is 6 hours — SEC 10-K supply chain data doesn't change intraday.
_VALAFI_CACHE: dict[str, tuple[list[dict], float]] = {}
_VALAFI_CACHE_TTL = 6 * 3600  # 6 hours


def _valafi_cache_clear():
    """Clear expired entries from the Vala-Fi cache."""
    now = time.time()
    expired = [k for k, (_, ts) in _VALAFI_CACHE.items() if now - ts > _VALAFI_CACHE_TTL]
    for k in expired:
        del _VALAFI_CACHE[k]


def fetch_supply_chain_from_valafi(ticker: str) -> list[dict]:
    """Fetch supply chain relationships from Vala-Fi (SEC 10-K extraction).

    Results cached for 6 hours to respect the 50 requests/day API limit.
    """
    ticker_u = ticker.upper()

    # Check cache
    _valafi_cache_clear()
    if ticker_u in _VALAFI_CACHE:
        return _VALAFI_CACHE[ticker_u][0]

    raw = _valafi_get(f"/company/{ticker_u}/supply-chain")
    if not raw:
        _VALAFI_CACHE[ticker_u] = ([], time.time())
        return []

    relationships: list[dict] = []

    for item in raw.get("suppliers", []):
        target_info = item.get("target", {})
        source_info = item.get("source", {})
        target = (target_info.get("ticker") or "").upper().strip()
        source = (source_info.get("ticker") or "").upper().strip()
        rel_type = (item.get("relationship_type") or "").lower()

        if source == ticker_u:
            other = target
            if rel_type == "customer":
                rtype = "customer"
            elif rel_type == "supplier":
                rtype = "supplier"
            else:
                rtype = "partner"
        elif target == ticker_u:
            other = source
            if rel_type == "customer":
                rtype = "supplier"
            elif rel_type == "supplier":
                rtype = "customer"
            else:
                rtype = "partner"
        else:
            continue

        if not other or other == ticker_u:
            continue

        evidence = item.get("evidence") or item.get("description", "")
        confidence = item.get("confidence", 0)
        strength = "strong" if confidence >= 0.7 else "medium" if confidence >= 0.4 else "weak"

        relationships.append({
            "source": ticker_u,
            "target": other,
            "type": rtype,
            "description": evidence,
            "strength": strength,
            "source_detail": "Vala-Fi / SEC Filing",
        })

    _VALAFI_CACHE[ticker_u] = (relationships, time.time())
    return relationships


def fetch_path_from_valafi(ticker_a: str, ticker_b: str) -> list[dict] | None:
    """Find shortest supply chain path between two companies."""
    raw = _valafi_get(f"/path/{ticker_a.upper()}/{ticker_b.upper()}")
    if not raw:
        return None
    return raw.get("path", [])


def fetch_exposure_from_valafi(ticker: str) -> dict | None:
    """Get supply chain concentration risk from Vala-Fi."""
    return _valafi_get(f"/exposure/{ticker.upper()}")


# ---------------------------------------------------------------------------
# Country risk
# ---------------------------------------------------------------------------

@lru_cache(maxsize=1)
def load_country_risk() -> dict:
    """Load and cache country risk data from JSON."""
    path = os.path.join(os.path.dirname(__file__), "country_risk.json")
    with open(path) as f:
        return json.load(f)


def get_country_risk(country_code: str) -> dict | None:
    """Get risk data for a specific country by ISO code."""
    return load_country_risk().get(country_code.upper())


# ---------------------------------------------------------------------------
# Merged supply chain data (curated + API)
# ---------------------------------------------------------------------------

def get_enriched_relationships(ticker: str) -> dict:
    """Get ALL relationships for a ticker, merged from curated JSON + Vala-Fi API.

    Returns a dict with keys: suppliers, customers, competitors, partners,
    each a list of enriched relationship dicts.

    Curated data (company_links.json) takes priority for financial quantification.
    Vala-Fi data fills in additional relationships not in the curated set.
    """
    ticker_u = ticker.upper().strip()

    # Clear stale cache since company_links.json may have been updated
    load_relationships.cache_clear()

    # Load curated relationships for this ticker
    curated = get_relationships_for_ticker(ticker_u)

    # Try Vala-Fi for additional relationships
    valafi = fetch_supply_chain_from_valafi(ticker_u)

    # Merge: curated takes priority. Deduplicate by (type, other_ticker)
    seen = set()
    # Map singular type -> plural bucket key
    _TYPE_TO_BUCKET = {
        "supplier": "suppliers", "customer": "customers",
        "competitor": "competitors", "partner": "partners",
    }
    merged: dict[str, list[dict]] = {
        "suppliers": [], "customers": [], "competitors": [], "partners": [],
    }

    def _add(rel: dict):
        """Add a relationship to the merged dict, deduplicating."""
        other = rel["target"].upper() if rel["source"].upper() == ticker_u else rel["source"].upper()
        if not other or other == ticker_u:  # skip empty targets and self-references
            return
        rtype = rel.get("type", "partner")
        key = (rtype, other)
        if key in seen:
            return
        seen.add(key)
        bucket = _TYPE_TO_BUCKET.get(rtype, "partners")
        # Store enriched copy with 'other' field for display convenience
        merged[bucket].append({**rel, "other": other, "bucket": bucket})

    # Add curated first (priority)
    for rel in curated:
        _add(rel)

    # Add Vala-Fi data for relationships not already curated
    for rel in valafi:
        other = rel["target"].upper() if rel["source"].upper() == ticker_u else rel["source"].upper()
        key = (rel["type"], other)
        if key not in seen:
            _add(rel)

    return merged


def get_geo_breakdown(ticker: str) -> list[dict]:
    """Aggregate supply chain relationships by country.

    Returns list of dicts sorted by exposure count (desc):
      {country_code, country_name, supplier_count, customer_count,
       total_relationships, manufacturing_presence, risk_score, risk_label}
    """
    enriched = get_enriched_relationships(ticker)
    country_risk = load_country_risk()

    country_map: dict[str, dict] = {}

    for rel_type in ("suppliers", "customers", "competitors", "partners"):
        for rel in enriched.get(rel_type, []):
            geo = rel.get("target_geo") or {}
            domicile = geo.get("domicile", "??")
            manufacturing = geo.get("manufacturing", [])
            other = rel.get("other", rel.get("target", "??"))

            # By domicile
            if domicile not in country_map:
                risk = country_risk.get(domicile, {})
                country_map[domicile] = {
                    "country_code": domicile,
                    "country_name": risk.get("name", domicile),
                    "supplier_count": 0,
                    "customer_count": 0,
                    "competitor_count": 0,
                    "partner_count": 0,
                    "total_relationships": 0,
                    "companies": [],
                    "manufacturing_presence": len(manufacturing) > 0,
                    "risk_score": risk.get("risk_score"),
                    "risk_label": risk.get("risk_label", "Unknown"),
                    "geo_political_risk": risk.get("geo_political_risk", ""),
                    "sanctions_flag": risk.get("sanctions_flag", False),
                }
            # Increment counts exactly once per relationship-type
            bucket = rel_type[:-1]  # "suppliers" -> "supplier"
            country_map[domicile][f"{bucket}_count"] = \
                country_map[domicile].get(f"{bucket}_count", 0) + 1
            country_map[domicile]["total_relationships"] += 1
            # Track which companies are in each country (for drill-down)
            if other not in country_map[domicile]["companies"]:
                country_map[domicile]["companies"].append(other)

            # Manufacturing locations
            for mfg in manufacturing:
                if mfg not in country_map:
                    risk = country_risk.get(mfg, {})
                    country_map[mfg] = {
                        "country_code": mfg,
                        "country_name": risk.get("name", mfg),
                        "supplier_count": 0,
                        "customer_count": 0,
                        "competitor_count": 0,
                        "partner_count": 0,
                        "total_relationships": 0,
                        "companies": [],
                        "manufacturing_presence": True,
                        "risk_score": risk.get("risk_score"),
                        "risk_label": risk.get("risk_label", "Unknown"),
                        "geo_political_risk": risk.get("geo_political_risk", ""),
                        "sanctions_flag": risk.get("sanctions_flag", False),
                    }

    return sorted(country_map.values(), key=lambda x: -x["total_relationships"])


def compute_exposure_summary(ticker: str) -> dict:
    """Compute a top-level supply chain exposure summary for display.

    Returns:
      - total_suppliers, total_customers, total_competitors, total_partners
      - supplier_concentration_pct: % of COGS accounted for by known suppliers
      - customer_concentration_pct: % of revenue from known customers
      - top_supplier, top_customer (by financial magnitude)
      - dominant_country: country with most relationships
      - riskiest_country: highest risk score country in the chain
      - critical_dependency_flag: true if >30% COGS from single supplier
    """
    enriched = get_enriched_relationships(ticker)
    geo_breakdown = get_geo_breakdown(ticker)

    suppliers = enriched.get("suppliers", [])
    customers = enriched.get("customers", [])

    supplier_cogs = 0.0
    top_supplier = None
    top_supplier_pct = 0.0
    for s in suppliers:
        fin = s.get("financials") or {}
        pct = fin.get("cogs_pct", 0)
        supplier_cogs += pct
        if pct > top_supplier_pct:
            top_supplier_pct = pct
            top_supplier = {"ticker": s.get("other", s["target"]), "cogs_pct": pct, "name": s.get("description", "")}

    customer_revenue = 0.0
    top_customer = None
    top_customer_pct = 0.0
    for c in customers:
        fin = c.get("financials") or {}
        pct = fin.get("revenue_pct", 0)
        customer_revenue += pct
        if pct > top_customer_pct:
            top_customer_pct = pct
            top_customer = {"ticker": c.get("other", c["target"]), "revenue_pct": pct, "name": c.get("description", "")}

    dominant_country = geo_breakdown[0] if geo_breakdown else None
    riskiest = max(geo_breakdown, key=lambda x: x.get("risk_score") or 0) if geo_breakdown else None

    return {
        "total_suppliers": len(suppliers),
        "total_customers": len(customers),
        "total_competitors": len(enriched.get("competitors", [])),
        "total_partners": len(enriched.get("partners", [])),
        "supplier_cogs_pct": round(supplier_cogs, 1),
        "customer_revenue_pct": round(customer_revenue, 1),
        "top_supplier": top_supplier,
        "top_customer": top_customer,
        "dominant_country": dominant_country,
        "riskiest_country": riskiest,
        "critical_dependency_flag": top_supplier_pct > 30,
        "critical_dependency_detail": (
            f">{top_supplier_pct:.0f}% COGS from {top_supplier['ticker']}"
            if top_supplier_pct > 30 and top_supplier else None
        ),
    }
