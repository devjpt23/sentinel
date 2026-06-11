"""
Loader for curated inter-company relationships.
Provides query functions for the company linkage feature.

Relationships are stored in company_links.json and include:
  - supplier: company A supplies goods/services to company B
  - customer: company A is a customer of company B
  - competitor: companies compete in the same market
  - partner: companies collaborate or have strategic partnerships
  - investor: company A has a significant investment in company B
"""

import json
import os
from functools import lru_cache

@lru_cache(maxsize=1)
def load_relationships() -> list[dict]:
    """Load and cache all relationships from JSON.

    Returns a list of relationship dicts, each with:
        source, target, type, description, strength
    """
    path = os.path.join(os.path.dirname(__file__), "company_links.json")
    with open(path, "r") as f:
        return json.load(f)


def get_relationships_for_ticker(ticker: str) -> list[dict]:
    """Get all relationships where the given ticker appears as source OR target.

    The check is symmetric — if NVDA→AMD is stored, querying "AMD" will find it.
    """
    ticker_upper = ticker.upper().strip()
    all_rels = load_relationships()
    return [
        r for r in all_rels
        if r["source"].upper() == ticker_upper or r["target"].upper() == ticker_upper
    ]


def get_relationships_in_group(tickers: list[str]) -> list[dict]:
    """Get all relationships where BOTH source and target are in the given ticker list.

    This filters to relationships that exist WITHIN a sector or industry group,
    which is the primary use case for the sector search page.
    """
    ticker_set = set(t.upper().strip() for t in tickers)
    all_rels = load_relationships()
    return [
        r for r in all_rels
        if r["source"].upper() in ticker_set and r["target"].upper() in ticker_set
    ]


def get_relationship_types() -> list[str]:
    """Return the valid relationship types for UI display/filtering."""
    return ["supplier", "customer", "competitor", "partner", "investor"]
