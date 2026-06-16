"""
SEC EDGAR direct API integration — lightweight fallback for SEC Filings
and Insider Trading when OpenBB is not installed.

Uses only Python stdlib (urllib, json). No API key required.
SEC EDGAR API: https://www.sec.gov/edgar/searchedgar/companyticker.html
"""

import json
import os
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Optional

import pandas as pd

USER_AGENT = "SentinelApp/1.0 (contact@example.com)"
BASE = "https://www.sec.gov"
DATA_BASE = "https://data.sec.gov"

# ── Helpers ─────────────────────────────────────────────────────────


def _edgar_request(url: str, timeout: int = 15) -> Optional[dict]:
    """Make an HTTP request to SEC EDGAR with proper User-Agent."""
    try:
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode())
    except Exception:
        return None


def _cache_dir() -> Path:
    base = os.environ.get("XDG_CACHE_HOME", str(Path.home() / ".cache"))
    d = Path(base) / "trade_proj" / "edgar_cache"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _cache_get(key: str, max_age: int = 3600) -> Optional[Any]:
    """Read from disk cache."""
    import pickle

    path = _cache_dir() / f"{key}.pickle"
    if not path.exists():
        return None
    try:
        entry = pickle.loads(path.read_bytes())
        if time.time() - entry["ts"] < max_age:
            return entry["data"]
        path.unlink(missing_ok=True)
    except Exception:
        path.unlink(missing_ok=True)
    return None


def _cache_set(key: str, data: object, ttl: int = 3600) -> None:
    """Write to disk cache."""
    import pickle

    try:
        entry = {"ts": time.time(), "data": data}
        (_cache_dir() / f"{key}.pickle").write_bytes(pickle.dumps(entry))
    except Exception:
        pass


# ── Ticker → CIK mapping ──────────────────────────────────────────

_TICKER_CIK_CACHE_KEY = "ticker_cik_map"
_TICKER_CIK_CACHE_TTL = 86400 * 7  # 7 days


def _build_ticker_cik_map() -> Optional[dict[str, int]]:
    """Download the full ticker→CIK mapping from SEC EDGAR."""
    ck = _TICKER_CIK_CACHE_KEY
    cached = _cache_get(ck, max_age=_TICKER_CIK_CACHE_TTL)
    if cached is not None:
        return cached

    data = _edgar_request(f"{BASE}/files/company_tickers.json")
    if data is None:
        return None

    result = {v["ticker"].upper(): v["cik_str"] for v in data.values()}
    _cache_set(ck, result, ttl=_TICKER_CIK_CACHE_TTL)
    return result


def _get_cik(ticker: str) -> Optional[str]:
    """Get CIK (10-digit zero-padded) for a ticker."""
    mapping = _build_ticker_cik_map()
    if mapping is None:
        return None
    cik = mapping.get(ticker.upper())
    if cik is None:
        return None
    return str(cik).zfill(10)


# ── SEC Filings ────────────────────────────────────────────────────

_KEY_REPORT_TYPES = {
    "10-K", "10-Q", "8-K", "10-K/A", "10-Q/A", "8-K/A",
    "20-F", "6-K", "S-1", "S-3", "DEF 14A",
}


def fetch_sec_filings_edgar(
    ticker: str, limit: int = 20
) -> Optional[pd.DataFrame]:
    """Fetch recent SEC filings for a ticker via EDGAR submissions API.

    Returns DataFrame with: filing_date, report_type, report_url, filing_detail_url
    """
    cik = _get_cik(ticker)
    if cik is None:
        return None

    ck = f"edgar_filings_{ticker.upper()}"
    cached = _cache_get(ck, max_age=3600)
    if cached is not None:
        return cached

    data = _edgar_request(f"{DATA_BASE}/submissions/CIK{cik}.json")
    if data is None:
        return None

    recent = data.get("filings", {}).get("recent", {})
    if not recent:
        return None

    forms = recent.get("form", [])
    dates = recent.get("filingDate", [])
    accs = recent.get("accessionNumber", [])

    rows = []
    for i in range(len(forms)):
        if forms[i] not in _KEY_REPORT_TYPES:
            continue
        # Accession numbers come without dashes in the API
        acc_raw = accs[i]
        report_url = (
            f"{BASE}/Archives/edgar/data/{cik}/{acc_raw}"
        )
        detail_url = (
            f"{BASE}/cgi-bin/browse-edgar?action=getcompany"
            f"&CIK={cik}&type={forms[i]}&count=100&search=&owner=include"
            f"&action=getcompany"
        )
        rows.append({
            "filing_date": dates[i],
            "report_type": forms[i],
            "report_url": report_url,
            "filing_detail_url": detail_url,
        })
        if len(rows) >= limit:
            break

    if not rows:
        return None

    df = pd.DataFrame(rows)
    _cache_set(ck, df, ttl=3600)
    return df


# ── Insider Trading ───────────────────────────────────────────────

def fetch_insider_trading_edgar(
    ticker: str, limit: int = 50
) -> Optional[pd.DataFrame]:
    """Fetch insider trading (Form 4) data via EDGAR full-text search.

    Returns DataFrame with: owner_name, transaction_type, transaction_date,
    shares, price, filing_url, owner_title
    """
    cik = _get_cik(ticker)
    if cik is None:
        return None

    ck = f"edgar_insider_{ticker.upper()}"
    cached = _cache_get(ck, max_age=3600)
    if cached is not None:
        return cached

    # Get recent Form 4 filings from the submissions endpoint
    data = _edgar_request(f"{DATA_BASE}/submissions/CIK{cik}.json")
    if data is None:
        return None

    recent = data.get("filings", {}).get("recent", {})
    if not recent:
        return None

    forms = recent.get("form", [])
    dates = recent.get("filingDate", [])
    accs = recent.get("accessionNumber", [])

    rows = []
    for i in range(len(forms)):
        if forms[i] != "4":
            continue
        acc_raw = accs[i]
        filing_url = f"{BASE}/Archives/edgar/data/{cik}/{acc_raw}"
        rows.append({
            "owner_name": "",  # Requires parsing the XML
            "transaction_type": "Form 4",
            "transaction_date": dates[i],
            "shares": None,
            "price": None,
            "filing_url": filing_url,
            "owner_title": "",
        })
        if len(rows) >= limit:
            break

    if not rows:
        return None

    df = pd.DataFrame(rows)
    _cache_set(ck, df, ttl=3600)
    return df
