"""
Loader for the sector universe (static company listings from S&P 500 + Nasdaq 100).
Provides search and filter functions for the Sector Search feature.

Data source: Wikipedia "List of S&P 500 companies" table, with GICS sectors/industries.
Supplemented with key Nasdaq 100 names not in the S&P 500.
"""

import json
import os
from functools import lru_cache
from typing import Optional


@lru_cache(maxsize=1)
def load_universe() -> list[dict]:
    """Load and cache the full company universe from JSON.

    Returns a list of dicts, each with: ticker, name, sector, industry.
    The JSON is ~80KB and parses in ~2ms — the lru_cache ensures it's
    read from disk only once per process.
    """
    path = os.path.join(os.path.dirname(__file__), "sector_universe.json")
    with open(path, "r") as f:
        return json.load(f)


def get_all_sectors() -> list[str]:
    """Return sorted list of unique sector names across the universe."""
    companies = load_universe()
    sectors = sorted(set(c["sector"] for c in companies if c.get("sector")))
    return sectors


def get_all_industries() -> list[str]:
    """Return sorted list of unique industry names across the universe."""
    companies = load_universe()
    industries = sorted(set(c["industry"] for c in companies if c.get("industry")))
    return industries


def search_sectors(query: str) -> list[str]:
    """Search for matching sector names given a user query.

    Matches against both sector and industry fields (case-insensitive substring).
    Returns a sorted, deduplicated list of sector names that contain matching companies.

    Examples:
        search_sectors("tech")      → ["Information Technology"]
        search_sectors("semicon")   → ["Information Technology"]  (matches industry "Semiconductors")
        search_sectors("health")    → ["Health Care"]
    """
    query_lower = query.strip().lower()
    if not query_lower:
        return []

    companies = load_universe()
    matched_sectors = set()
    for c in companies:
        sector = c.get("sector", "")
        industry = c.get("industry", "")
        if query_lower in sector.lower() or query_lower in industry.lower():
            matched_sectors.add(sector)

    # Sort by relevance: shorter sector names first (closer to what user typed),
    # then alphabetically as tiebreaker
    return sorted(matched_sectors, key=lambda x: (len(x), x.lower()))


def search_industries(query: str, sector: Optional[str] = None) -> list[str]:
    """Search for matching industry names.

    Args:
        query: Substring to match against industry names (case-insensitive).
        sector: If provided, only return industries within this sector.

    Returns a sorted, deduplicated list of matching industry names.
    """
    query_lower = query.strip().lower()
    if not query_lower:
        return []

    companies = load_universe()
    matched = set()
    for c in companies:
        industry = c.get("industry", "")
        if query_lower not in industry.lower():
            continue
        if sector and c.get("sector", "").lower() != sector.lower():
            continue
        matched.add(industry)

    # Sort by relevance: shorter names first (closer to what user typed),
    # then alphabetically as tiebreaker
    return sorted(matched, key=lambda x: (len(x), x.lower()))


def get_companies_in_sector(sector_name: str) -> list[dict]:
    """Get all companies in a given GICS sector (case-insensitive exact match)."""
    companies = load_universe()
    sector_lower = sector_name.strip().lower()
    return [c for c in companies if c.get("sector", "").lower() == sector_lower]


def get_companies_in_industry(industry_name: str) -> list[dict]:
    """Get all companies in a given GICS sub-industry (case-insensitive exact match)."""
    companies = load_universe()
    industry_lower = industry_name.strip().lower()
    return [c for c in companies if c.get("industry", "").lower() == industry_lower]


def get_industries_for_sector(sector_name: str) -> list[str]:
    """Return sorted list of unique industry names within a given sector."""
    companies = get_companies_in_sector(sector_name)
    industries = sorted(set(c["industry"] for c in companies if c.get("industry")))
    return industries


def get_companies_matching(search: str) -> list[dict]:
    """Broad search across ticker, name, sector, and industry.

    Useful for when the user types a partial company name or ticker.
    """
    q = search.strip().lower()
    if not q:
        return []
    companies = load_universe()
    results = []
    for c in companies:
        if (q in c.get("ticker", "").lower()
                or q in c.get("name", "").lower()
                or q in c.get("sector", "").lower()
                or q in c.get("industry", "").lower()):
            results.append(c)
    return results
