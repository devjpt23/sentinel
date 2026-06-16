"""
OpenBB-based data fetching layer.

Provides a parallel data backend to fetcher.py, using the OpenBB Python SDK
(``from openbb import obb``) to access multiple data providers through a
single unified API.

Default provider is ``yfinance`` (no API key required) for maximum
out-of-the-box compatibility.  Users with FMP, Intrinio, or Polygon keys
can set them via OpenBB's configuration and get richer data.

Caching mirrors the patterns in ``fetcher.py``:
  - In-memory LRU for hot lookups
  - Persistent pickle disk cache (survives restarts)
  - Token-bucket rate limiter to respect provider limits
"""

import hashlib
import os
import pickle
import threading
import time
from datetime import date, datetime
from functools import lru_cache
from pathlib import Path
from typing import Optional, Dict, Any, List

import pandas as pd

try:
    from openbb import obb  # noqa: F401
    OPENBB_AVAILABLE = True
except ImportError:
    obb = None  # type: ignore[misc, assignment]
    OPENBB_AVAILABLE = False

# ═══════════════════════════════════════════════════════════════
#  Rate limiter (simple token-bucket, thread-safe)
# ═══════════════════════════════════════════════════════════════


class _RateLimiter:
    """Token-bucket rate limiter — ~2 calls/sec to stay well under limits."""

    def __init__(self, calls_per_second: float = 2.0):
        self._min_interval = 1.0 / calls_per_second
        self._lock = threading.Lock()
        self._last_call = 0.0

    def wait(self):
        with self._lock:
            now = time.monotonic()
            wait = self._last_call + self._min_interval - now
            if wait > 0:
                time.sleep(wait)
            self._last_call = time.monotonic()


_rate_limiter = _RateLimiter(calls_per_second=2.0)


# ═══════════════════════════════════════════════════════════════
#  Disk cache (mirrors fetcher.py pattern)
# ═══════════════════════════════════════════════════════════════


def _cache_dir() -> Path:
    base = os.environ.get("XDG_CACHE_HOME", str(Path.home() / ".cache"))
    d = Path(base) / "trade_proj" / "obb_cache"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _cache_key(*parts: str) -> str:
    return hashlib.md5("|".join(parts).encode()).hexdigest()


def _disk_cache_get(key: str, max_age_seconds: int = 300) -> Optional[Any]:
    path = _cache_dir() / f"{key}.pickle"
    if not path.exists():
        return None
    try:
        entry = pickle.loads(path.read_bytes())
        if time.time() - entry["ts"] < max_age_seconds:
            return entry["data"]
        path.unlink(missing_ok=True)
    except Exception:
        path.unlink(missing_ok=True)
    return None


def _disk_cache_set(key: str, data: Any) -> None:
    try:
        entry = {"ts": time.time(), "data": data}
        (_cache_dir() / f"{key}.pickle").write_bytes(pickle.dumps(entry))
    except Exception:
        pass


# In-memory hot cache
_memory_cache: dict[str, tuple[float, Any]] = {}
_memory_lock = threading.Lock()
_MEMORY_MAXSIZE = 64


def _cached_obb_call(cache_prefix: str, cache_key_str: str,
                     fetcher_fn, max_age: int = 300):
    """Generic caching wrapper for OpenBB calls.

    Checks in-memory → disk → live API call (with rate limiting).
    ``fetcher_fn`` is a zero-argument callable that performs the OpenBB call.
    """
    ck = _cache_key(cache_prefix, cache_key_str)

    # 1. In-memory
    with _memory_lock:
        if ck in _memory_cache:
            ts, data = _memory_cache[ck]
            if time.time() - ts < max_age:
                return data

    # 2. Disk
    disk_val = _disk_cache_get(ck, max_age_seconds=max_age)
    if disk_val is not None:
        with _memory_lock:
            _memory_cache[ck] = (time.time(), disk_val)
            if len(_memory_cache) > _MEMORY_MAXSIZE:
                # Evict oldest
                oldest = min(_memory_cache, key=lambda k: _memory_cache[k][0])
                del _memory_cache[oldest]
        return disk_val

    # 3. Live call
    _rate_limiter.wait()
    result = fetcher_fn()

    # Store
    _disk_cache_set(ck, result)
    with _memory_lock:
        _memory_cache[ck] = (time.time(), result)
        if len(_memory_cache) > _MEMORY_MAXSIZE:
            oldest = min(_memory_cache, key=lambda k: _memory_cache[k][0])
            del _memory_cache[oldest]

    return result


# ═══════════════════════════════════════════════════════════════
#  Provider helper: try FMP first, fall back to yfinance
# ═══════════════════════════════════════════════════════════════

def _try_providers(*fns):
    """Try each provider function in order, return first non-None result."""
    for fn in fns:
        try:
            result = fn()
            if result is not None:
                return result
        except Exception:
            continue
    return None


# ═══════════════════════════════════════════════════════════════
#  Helper: OBBject → safe DataFrame / dict
# ═══════════════════════════════════════════════════════════════


def _safe_to_df(obbject) -> Optional[pd.DataFrame]:
    """Convert an OBBject to DataFrame, returning None on failure."""
    try:
        if obbject is None:
            return None
        df = obbject.to_df()
        if df is None or df.empty:
            return None
        return df
    except Exception:
        return None


def _safe_first_row(obbject) -> Optional[dict]:
    """Get first row of an OBBject as a dict, returning None on failure."""
    try:
        df = _safe_to_df(obbject)
        if df is not None and len(df) > 0:
            return df.iloc[0].to_dict()
    except Exception:
        pass
    return None


# ═══════════════════════════════════════════════════════════════
#  Company Profile
# ═══════════════════════════════════════════════════════════════


def fetch_company_profile_obb(ticker: str) -> Optional[Dict[str, Any]]:
    """Get general company info via OpenBB — FMP preferred, yfinance fallback.

    Returns a dict compatible with the ``company`` and ``market`` sub-dicts
    expected by the dashboard.
    """
    if not OPENBB_AVAILABLE:
        return None

    def _fetch():
        row = _try_providers(
            lambda: _safe_first_row(obb.equity.profile(
                symbol=ticker.upper(), provider="fmp")),
            lambda: _safe_first_row(obb.equity.profile(
                symbol=ticker.upper(), provider="yfinance")),
        )
        if row is None:
            return None
        return {
            "ticker": ticker.upper(),
            "name": row.get("name") or ticker.upper(),
            "sector": row.get("sector", "N/A"),
            "industry": row.get("industry_category", "N/A"),
            "employees": row.get("employees"),
            "description": row.get("long_description", ""),
            "website": row.get("company_url", ""),
            "country": row.get("hq_country", ""),
            "market_cap": row.get("market_cap"),
            "shares_outstanding": row.get("shares_outstanding"),
            "beta": row.get("beta"),
            "dividend_yield": (
                row.get("dividend_yield") / 100
                if row.get("dividend_yield") is not None
                else None
            ),
        }

    return _cached_obb_call("profile", ticker.upper(), _fetch, max_age=300)


# ═══════════════════════════════════════════════════════════════
#  Key Financial Metrics
# ═══════════════════════════════════════════════════════════════


def fetch_financial_metrics_obb(ticker: str) -> Optional[Dict[str, Any]]:
    """Get key financial metrics (P/E, ROE, margins, growth, etc.).

    Tries FMP first (richer data), falls back to yfinance.
    Returns a flat dict of the most recent annual period.
    """
    if not OPENBB_AVAILABLE:
        return None

    def _fetch():
        row = _try_providers(
            lambda: _safe_first_row(obb.equity.fundamental.metrics(
                symbol=ticker.upper(), provider="fmp", period="annual", limit=1)),
            lambda: _safe_first_row(obb.equity.fundamental.metrics(
                symbol=ticker.upper(), provider="yfinance", period="annual", limit=1)),
        )
        return row  # flat dict of all metrics

    return _cached_obb_call("metrics", ticker.upper(), _fetch, max_age=300)


# ═══════════════════════════════════════════════════════════════
#  Financial Statements
# ═══════════════════════════════════════════════════════════════


def fetch_income_stmt_obb(ticker: str, limit: int = 4) -> Optional[pd.DataFrame]:
    """Income statement (annual) via OpenBB — FMP preferred, yfinance fallback."""
    if not OPENBB_AVAILABLE:
        return None

    def _fetch():
        return _try_providers(
            lambda: _safe_to_df(obb.equity.fundamental.income(
                symbol=ticker.upper(), provider="fmp", period="annual", limit=limit)),
            lambda: _safe_to_df(obb.equity.fundamental.income(
                symbol=ticker.upper(), provider="yfinance", period="annual", limit=limit)),
        )
    return _cached_obb_call("income", f"{ticker.upper()}:{limit}", _fetch, max_age=300)


def fetch_balance_sheet_obb(ticker: str, limit: int = 4) -> Optional[pd.DataFrame]:
    """Balance sheet (annual) via OpenBB — FMP preferred, yfinance fallback."""
    if not OPENBB_AVAILABLE:
        return None

    def _fetch():
        return _try_providers(
            lambda: _safe_to_df(obb.equity.fundamental.balance(
                symbol=ticker.upper(), provider="fmp", period="annual", limit=limit)),
            lambda: _safe_to_df(obb.equity.fundamental.balance(
                symbol=ticker.upper(), provider="yfinance", period="annual", limit=limit)),
        )
    return _cached_obb_call("balance", f"{ticker.upper()}:{limit}", _fetch, max_age=300)


def fetch_cash_flow_obb(ticker: str, limit: int = 4) -> Optional[pd.DataFrame]:
    """Cash flow statement (annual) via OpenBB — FMP preferred, yfinance fallback."""
    if not OPENBB_AVAILABLE:
        return None

    def _fetch():
        return _try_providers(
            lambda: _safe_to_df(obb.equity.fundamental.cash(
                symbol=ticker.upper(), provider="fmp", period="annual", limit=limit)),
            lambda: _safe_to_df(obb.equity.fundamental.cash(
                symbol=ticker.upper(), provider="yfinance", period="annual", limit=limit)),
        )
    return _cached_obb_call("cashflow", f"{ticker.upper()}:{limit}", _fetch, max_age=300)


# ═══════════════════════════════════════════════════════════════
#  Analyst Estimates (net-new capability — richer than yfinance)
# ═══════════════════════════════════════════════════════════════


def fetch_analyst_consensus_obb(ticker: str) -> Optional[Dict[str, Any]]:
    """Fetch analyst consensus via OpenBB — FMP preferred, yfinance fallback.

    Returns: target_high, target_low, target_consensus, target_median,
             recommendation (buy/hold/sell), recommendation_mean,
             number_of_analysts, current_price.
    """
    if not OPENBB_AVAILABLE:
        return None

    def _fetch():
        row = _try_providers(
            lambda: _safe_first_row(obb.equity.estimates.consensus(
                symbol=ticker.upper(), provider="fmp")),
            lambda: _safe_first_row(obb.equity.estimates.consensus(
                symbol=ticker.upper(), provider="yfinance")),
        )
        if row is None:
            return None

        # Normalize to match existing analyst data structure
        price = row.get("current_price")
        consensus = row.get("target_consensus")
        upside_pct = None
        if consensus and price and price > 0:
            upside_pct = ((consensus - price) / price) * 100

        return {
            "price_targets": {
                "current": price,
                "low": row.get("target_low"),
                "mean": row.get("target_consensus"),
                "median": row.get("target_median"),
                "high": row.get("target_high"),
                "upside_pct": upside_pct,
            },
            "num_analysts": row.get("number_of_analysts"),
            "recommendation": row.get("recommendation"),
            "recommendation_mean": row.get("recommendation_mean"),
        }

    return _cached_obb_call("analyst", ticker.upper(), _fetch, max_age=600)


# ═══════════════════════════════════════════════════════════════
#  Price Data
# ═══════════════════════════════════════════════════════════════


def fetch_price_quote_obb(ticker: str) -> Optional[Dict[str, Any]]:
    """Live price quote via OpenBB yfinance provider."""
    if not OPENBB_AVAILABLE:
        return None

    def _fetch():
        result = obb.equity.price.quote(symbol=ticker.upper(), provider="yfinance")
        return _safe_first_row(result)

    return _cached_obb_call("quote", ticker.upper(), _fetch, max_age=30)


def fetch_price_history_obb(ticker: str, period: str = "5y") -> Optional[pd.DataFrame]:
    """Historical daily prices via OpenBB yfinance provider."""
    if not OPENBB_AVAILABLE:
        return None

    def _fetch():
        result = obb.equity.price.historical(
            symbol=ticker.upper(), provider="yfinance"
        )
        df = _safe_to_df(result)
        if df is not None and "date" in df.columns:
            df = df.set_index("date")
        return df

    return _cached_obb_call("history", f"{ticker.upper()}:{period}", _fetch, max_age=300)


# ═══════════════════════════════════════════════════════════════
#  Stock Screener (Phase 3)
# ═══════════════════════════════════════════════════════════════

SUPPORTED_SCREENER_COUNTRIES = [
    "all", "ar", "at", "au", "be", "br", "ca", "ch", "cl", "cn", "cz",
    "de", "dk", "ee", "eg", "es", "fi", "fr", "gb", "gr", "hk", "hu",
    "id", "ie", "il", "in", "is", "it", "jp", "kr", "kw", "lk", "lt",
    "lv", "mx", "my", "nl", "no", "nz", "pe", "ph", "pk", "pl", "pt",
    "qa", "ro", "ru", "sa", "se", "sg", "sr", "th", "tr", "tw", "us",
    "ve", "vn", "za",
]


def fetch_screener_obb(country: str = "us") -> Optional[pd.DataFrame]:
    """Stock screener — top movers for a country via OpenBB yfinance provider.

    Returns up to 200 stocks with price, change, market cap, P/E, etc.
    """
    if not OPENBB_AVAILABLE:
        return None

    country = country.lower()
    if country not in SUPPORTED_SCREENER_COUNTRIES:
        country = "us"

    def _fetch():
        result = obb.equity.screener(provider="yfinance", country=country)
        return _safe_to_df(result)

    return _cached_obb_call("screener", country, _fetch, max_age=120)



# ═══════════════════════════════════════════════════════════════
#  SEC Filings (Phase 3) — free, no API key required
# ═══════════════════════════════════════════════════════════════


def fetch_sec_filings_obb(
    ticker: str, limit: int = 20
) -> Optional[pd.DataFrame]:
    """Recent SEC filings for a ticker via OpenBB SEC provider (free).

    Returns: filing_date, report_type, report_url, filing_detail_url, etc.
    Filters to 10-K, 10-Q, 8-K report types.
    """
    if not OPENBB_AVAILABLE:
        return None

    def _fetch():
        result = obb.equity.fundamental.filings(
            symbol=ticker.upper(), provider="sec"
        )
        df = _safe_to_df(result)
        if df is not None:
            # Filter to key report types
            keep = df["report_type"].isin(
                ["10-K", "10-Q", "8-K", "10-K/A", "10-Q/A", "8-K/A",
                 "20-F", "6-K", "S-1", "S-3"]
            )
            df = df[keep].head(limit)
        return df

    return _cached_obb_call("sec_filings", ticker.upper(), _fetch, max_age=3600)


# ═══════════════════════════════════════════════════════════════
#  Insider Trading (Phase 3) — free with SEC provider
# ═══════════════════════════════════════════════════════════════


def fetch_insider_trading_obb(
    ticker: str, limit: int = 50
) -> Optional[pd.DataFrame]:
    """Insider trading transactions via OpenBB SEC provider (free).

    Returns: owner_name, transaction_type, transaction_date, shares,
             price, filing_url, owner_title, etc.

    Note: This endpoint downloads SEC filings so it can be slow (~5-15 s).
    """
    if not OPENBB_AVAILABLE:
        return None

    def _fetch():
        result = obb.equity.ownership.insider_trading(
            symbol=ticker.upper(), provider="sec", limit=limit
        )
        return _safe_to_df(result)

    return _cached_obb_call("insider", ticker.upper(), _fetch, max_age=3600)


# ═══════════════════════════════════════════════════════════════
#  Composite: Full company data (Phase 2 fallback)
# ═══════════════════════════════════════════════════════════════


def fetch_company_data_via_openbb(ticker: str) -> Optional[Dict[str, Any]]:
    """Build a fetcher.py-compatible company data dict from OpenBB endpoints.

    This is the fallback used when yfinance's raw ``.info`` dict fails.
    It assembles ``company``, ``market``, ``valuation``, ``profitability``,
    ``health``, ``per_share``, and ``growth`` sub-dicts from multiple OBB calls.
    """
    t = ticker.upper()

    # Profile (company + market basics)
    profile = fetch_company_profile_obb(t)
    if profile is None:
        return None

    # Metrics (valuation, profitability, health, growth)
    metrics = fetch_financial_metrics_obb(t) or {}

    # Price quote for live market data
    quote = fetch_price_quote_obb(t) or {}

    # ── Assemble sub-dicts ──────────────────────────────

    company = {
        "ticker": t,
        "name": profile.get("name", t),
        "sector": profile.get("sector", "N/A"),
        "industry": profile.get("industry", "N/A"),
        "employees": profile.get("employees"),
        "description": profile.get("description", ""),
        "website": profile.get("website", ""),
        "country": profile.get("country", ""),
    }

    market = {
        "market_cap": profile.get("market_cap") or metrics.get("market_cap"),
        "beta": profile.get("beta") or metrics.get("beta"),
        "price": quote.get("last_price"),
        "previous_close": quote.get("prev_close"),
        "52w_high": quote.get("year_high"),
        "52w_low": quote.get("year_low"),
        "avg_volume": quote.get("volume_average"),
    }

    valuation = {
        "pe_ttm": metrics.get("pe_ratio"),
        "pe_forward": metrics.get("forward_pe"),
        "peg_ratio": metrics.get("peg_ratio") or metrics.get("peg_ratio_ttm"),
        "pb_ratio": metrics.get("price_to_book"),
        "ev_ebitda": metrics.get("enterprise_to_ebitda"),
        "ev_revenue": metrics.get("enterprise_to_revenue"),
        "enterprise_value": metrics.get("enterprise_value"),
        "graham_number": None,  # computed downstream
    }

    profitability = {
        "gross_margin": metrics.get("gross_margin"),
        "operating_margin": metrics.get("operating_margin"),
        "net_margin": metrics.get("profit_margin"),
        "roe": metrics.get("return_on_equity"),
        "roa": metrics.get("return_on_assets"),
        "roic": None,  # not directly available from metrics
    }

    health = {
        "debt_to_equity": metrics.get("debt_to_equity"),
        "current_ratio": metrics.get("current_ratio"),
        "quick_ratio": metrics.get("quick_ratio"),
        "fcf": None,  # needs separate cash flow endpoint
        "operating_cash_flow": None,
        "interest_coverage": None,
    }

    per_share = {
        "eps_ttm": None,
        "eps_forward": None,
        "revenue_per_share": metrics.get("revenue_per_share"),
        "book_value_per_share": metrics.get("book_value"),
        "dividend_yield": (
            metrics.get("dividend_yield") / 100
            if metrics.get("dividend_yield") is not None
            else profile.get("dividend_yield")
        ),
        "dividend_rate": None,
        "payout_ratio": metrics.get("payout_ratio"),
    }

    growth = {
        "revenue_growth_yoy": metrics.get("revenue_growth"),
        "earnings_growth_yoy": metrics.get("earnings_growth"),
        "earnings_growth_quarterly": metrics.get("earnings_growth_quarterly"),
    }

    return {
        "company": company,
        "market": market,
        "valuation": valuation,
        "profitability": profitability,
        "per_share": per_share,
        "growth": growth,
        "health": health,
        # financial statements not fetched here (they're for deep dive)
        "statements": {},
        "trends": {},
        "news": [],
        "_source": "openbb",  # marker so callers know this came from OBB
    }
