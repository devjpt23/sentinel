"""
Data fetching layer using yfinance.
Pulls all financial data needed for the dashboard.

Rate-limiting defences (added to stop Yahoo 429 / rate-limit errors):
  1. Shared requests.Session — connection pooling + auto-retry on 429/5xx
  2. Token-bucket rate limiter — ~2 req/s so bursts never exceed Yahoo's tolerance
  3. Persistent pickle disk cache — cuts repeat calls by ~90%, survives restarts
  4. In-memory info cache — sub-ms hot path for recently-accessed tickers
  5. Exponential backoff + jitter on failures
  6. Reduced worker counts + inter-request rate-limiter waits in batch fetches
"""

import hashlib
import os
import pickle
import random
import threading
import time
from functools import lru_cache
from pathlib import Path
from typing import Optional, Dict, Any

import numpy as np
import pandas as pd
import requests
import yfinance as yf
from concurrent.futures import ThreadPoolExecutor, as_completed
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# ═══════════════════════════════════════════════════════════════
#  Shared HTTP session — connection pooling, retry on 429/5xx
# ═══════════════════════════════════════════════════════════════

def _build_session() -> requests.Session:
    """Create a requests.Session tuned for Yahoo Finance.

    - Connection pooling (20) so repeated calls reuse sockets.
    - Automatic retry on 429 (Too Many Requests) + 5xx with backoff.
    - Realistic browser User-Agent so requests don't look scripted.
    """
    session = requests.Session()

    retry_strategy = Retry(
        total=3,
        backoff_factor=0.5,          # 0.5 s → 1 s → 2 s
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["GET", "HEAD"],
    )
    adapter = HTTPAdapter(
        max_retries=retry_strategy,
        pool_connections=20,
        pool_maxsize=20,
    )
    session.mount("https://", adapter)
    session.mount("http://", adapter)

    session.headers.update({
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
    })

    return session

_SESSION = _build_session()


# ═══════════════════════════════════════════════════════════════
#  Token-bucket rate limiter — prevents burst throttling
# ═══════════════════════════════════════════════════════════════

class _RateLimiter:
    """Simple token-bucket rate limiter, thread-safe.

    2 calls/second is conservative — well within Yahoo's ~2 000 req/hour
    limit while keeping the dashboard snappy.
    """

    def __init__(self, calls_per_second: float = 2.0):
        self._min_interval = 1.0 / calls_per_second
        self._lock = threading.Lock()
        self._last_call = 0.0

    def wait(self):
        """Block until the next call slot is available."""
        with self._lock:
            now = time.monotonic()
            wait = self._last_call + self._min_interval - now
            if wait > 0:
                time.sleep(wait)
            self._last_call = time.monotonic()

_rate_limiter = _RateLimiter(calls_per_second=2.0)


# ═══════════════════════════════════════════════════════════════
#  Persistent disk cache — survives app restarts
# ═══════════════════════════════════════════════════════════════

def _cache_dir() -> Path:
    """Cache directory, respecting XDG_CACHE_HOME if set."""
    base = os.environ.get("XDG_CACHE_HOME", str(Path.home() / ".cache"))
    d = Path(base) / "trade_proj" / "yf_cache"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _cache_key(*parts: str) -> str:
    """Deterministic cache key from string parts."""
    raw = "|".join(parts)
    return hashlib.md5(raw.encode()).hexdigest()


def _disk_cache_get(key: str, max_age_seconds: int = 300) -> Optional[Any]:
    """Read a value from the disk cache if it exists and is fresh."""
    path = _cache_dir() / f"{key}.pickle"
    if not path.exists():
        return None
    try:
        entry = pickle.loads(path.read_bytes())
        if time.time() - entry["ts"] < max_age_seconds:
            return entry["data"]
        # Stale — remove the file
        path.unlink(missing_ok=True)
    except Exception:
        path.unlink(missing_ok=True)
    return None


def _disk_cache_set(key: str, data: Any) -> None:
    """Write a value to the disk cache."""
    try:
        entry = {"ts": time.time(), "data": data}
        (_cache_dir() / f"{key}.pickle").write_bytes(pickle.dumps(entry))
    except Exception:
        pass  # cache write failure should never break the caller


# ═══════════════════════════════════════════════════════════════
#  Retry wrapper — exponential backoff + jitter
# ═══════════════════════════════════════════════════════════════

def _retry_with_backoff(fn, max_retries: int = 3, base_delay: float = 0.5):
    """Call *fn* with exponential backoff on any exception.

    Delay sequence: ~0.5 s → ~1 s → ~2 s (with jitter).
    Re-raises on final failure — callers should still wrap in try/except
    if they want graceful degradation.
    """
    for attempt in range(max_retries):
        try:
            return fn()
        except Exception:
            if attempt == max_retries - 1:
                raise
            wait = base_delay * (2 ** attempt) + random.uniform(0, 0.5)
            time.sleep(wait)


# ═══════════════════════════════════════════════════════════════
#  Cached ticker info — the workhorse of the module
# ═══════════════════════════════════════════════════════════════

# In-memory LRU for hot ticker-info lookups (fast path, avoids disk I/O).
_info_memory_cache: dict[str, tuple[float, dict]] = {}
_info_memory_lock = threading.Lock()
_INFO_MEMORY_MAXSIZE = 64


def _cached_ticker_info(ticker: str, max_age: int = 300) -> dict:
    """Return yfinance .info for *ticker*, with multi-layer caching.

    Layers (checked in order):
      1. In-memory LRU   — sub-millisecond, avoids disk I/O
      2. Disk pickle     — survives app restarts, ~1 ms
      3. Live API call   — rate-limited + retried

    Args:
        ticker: The ticker symbol (e.g. "AAPL").
        max_age: Max age in seconds before a cached value is considered stale.
                 Default 5 min balances freshness with rate-limit safety.
    """
    tkey = ticker.upper()

    # 1. In-memory cache
    with _info_memory_lock:
        if tkey in _info_memory_cache:
            ts, data = _info_memory_cache[tkey]
            if time.time() - ts < max_age:
                return data

    # 2. Disk cache
    disk_key = _cache_key("info", tkey)
    cached = _disk_cache_get(disk_key, max_age)
    if cached is not None:
        with _info_memory_lock:
            _info_memory_cache[tkey] = (time.time(), cached)
            _evict_lru_info()
        return cached

    # 3. Live fetch — rate-limited + retried
    _rate_limiter.wait()

    def _fetch():
        return yf.Ticker(tkey, session=_SESSION).info or {}

    try:
        info = _retry_with_backoff(_fetch)
    except Exception:
        info = {}

    # Persist
    if info:
        _disk_cache_set(disk_key, info)
        with _info_memory_lock:
            _info_memory_cache[tkey] = (time.time(), info)
            _evict_lru_info()

    return info


def _evict_lru_info():
    """Drop oldest entry when the in-memory info cache exceeds maxsize."""
    if len(_info_memory_cache) > _INFO_MEMORY_MAXSIZE:
        oldest = min(_info_memory_cache.items(), key=lambda kv: kv[1][0])
        del _info_memory_cache[oldest[0]]


# ═══════════════════════════════════════════════════════════════
#  Ticker factories — use the shared session
# ═══════════════════════════════════════════════════════════════

def _get_ticker(ticker: str) -> yf.Ticker:
    """Get a Ticker object wired to the shared session."""
    return yf.Ticker(ticker, session=_SESSION)


@lru_cache(maxsize=1)
def _get_macro_ticker(symbol: str) -> yf.Ticker:
    """Cached macro ticker — reuses the shared session."""
    return yf.Ticker(symbol, session=_SESSION)


# ═══════════════════════════════════════════════════════════════
#  Core analysis helpers
# ═══════════════════════════════════════════════════════════════

def _compute_roic(t: yf.Ticker) -> Optional[float]:
    """Compute ROIC = NOPAT / Invested Capital as a fallback when yfinance
    doesn't return returnOnCapital directly.

    NOPAT ≈ Operating Income × (1 - 0.21)
    Invested Capital = Total Equity + Total Debt - Cash
    """
    try:
        # Get operating income from financials
        income = t.financials
        if income is None or income.empty:
            return None

        op_income = None
        for label in income.index:
            lbl = str(label).strip()
            if "Operating Income" in lbl or "Operating" in lbl or lbl == "EBIT":
                vals = income.loc[label].dropna()
                if not vals.empty:
                    op_income = float(vals.iloc[0])
                    break

        if not op_income:
            return None

        # NOPAT ≈ Operating Income × (1 - tax rate), use 21% as standard
        nopat = op_income * (1 - 0.21)

        # Invested capital from balance sheet
        balance = t.balance_sheet
        if balance is None or balance.empty:
            return None

        total_equity = None
        total_debt = None
        cash = None

        for label in balance.index:
            lbl = str(label)
            if "Total Equity" in lbl or "Stockholders Equity" in lbl or "Shareholders Equity" in lbl:
                vals = balance.loc[label].dropna()
                if not vals.empty:
                    total_equity = float(vals.iloc[0])
            if "Total Debt" in lbl or "Long Term Debt" in lbl:
                vals = balance.loc[label].dropna()
                if not vals.empty:
                    total_debt = float(vals.iloc[0])
            if "Cash And" in lbl or "Cash &" in lbl or lbl == "Cash":
                vals = balance.loc[label].dropna()
                if not vals.empty:
                    cash = float(vals.iloc[0])

        if total_equity is not None and total_debt is not None:
            invested_capital = total_equity + total_debt - (cash or 0)
            if invested_capital > 0 and nopat > 0:
                return float(nopat / invested_capital)
    except Exception:
        pass
    return None


def _compute_52w_change(info: dict) -> Optional[float]:
    """Compute percent change from 52-week low to current price.

    Returns None if insufficient data, avoiding the / 1 fallback
    that previously produced garbage numbers when the 52-week low was missing.
    """
    low = info.get("fiftyTwoWeekLow")
    price = info.get("currentPrice") or info.get("regularMarketPrice")
    if low and price and low > 0:
        return ((price / low) - 1) * 100
    return None


# ═══════════════════════════════════════════════════════════════
#  Main company data fetch
# ═══════════════════════════════════════════════════════════════

def fetch_company_data(ticker: str) -> Dict[str, Any]:
    """Fetch all fundamental data for a given ticker.

    Returns a dictionary with everything the dashboard needs.
    Returns None for any field if data is unavailable.

    Uses _cached_ticker_info() for the .info dict (the heaviest API call).
    Financial statements and history are not disk-cached (they're only
    fetched on drill-down, not on every page load).
    """
    t = _get_ticker(ticker.upper())
    info = _cached_ticker_info(ticker)

    # --- Company Info ---
    company = {
        "ticker": ticker.upper(),
        "name": info.get("longName") or info.get("shortName", ticker),
        "sector": info.get("sector", "N/A"),
        "industry": info.get("industry", "N/A"),
        "employees": info.get("fullTimeEmployees"),
        "description": info.get("longBusinessSummary", ""),
        "website": info.get("website", ""),
        "country": info.get("country", ""),
    }

    # --- Market Data ---
    market = {
        "market_cap": info.get("marketCap"),
        "enterprise_value": info.get("enterpriseValue"),
        "shares_outstanding": info.get("sharesOutstanding"),
        "float": info.get("floatShares"),
        "beta": info.get("beta"),
        "price": info.get("currentPrice") or info.get("regularMarketPrice"),
        "previous_close": info.get("previousClose"),
        "52w_high": info.get("fiftyTwoWeekHigh"),
        "52w_low": info.get("fiftyTwoWeekLow"),
        "52w_change_pct": _compute_52w_change(info),
        "avg_volume": info.get("averageVolume"),
    }

    # --- Valuation Multiples ---
    valuation = {
        "pe_ttm": info.get("trailingPE"),
        "pe_forward": info.get("forwardPE"),
        "peg_ratio": info.get("pegRatio"),
        "pb_ratio": info.get("priceToBook"),
        "ps_ratio": info.get("priceToSalesTrailing12Months"),
        "ev_ebitda": info.get("enterpriseToEbitda"),
        "ev_revenue": info.get("enterpriseToRevenue"),
        "graham_number": None,  # computed below
    }

    # --- Profitability ---
    profitability = {
        "gross_margin": info.get("grossMargins"),
        "operating_margin": info.get("operatingMargins"),
        "net_margin": info.get("profitMargins"),
        "roe": info.get("returnOnEquity"),
        "roa": info.get("returnOnAssets"),
        "roic": info.get("returnOnCapital") or _compute_roic(t),
    }

    # --- Per Share ---
    # yfinance >=1.0 returns dividendYield as a percentage (e.g. 0.37 = 0.37%).
    # All downstream code expects a decimal (0.0037 = 0.37%), so we normalize here.
    _raw_div_yield = info.get("dividendYield")
    per_share = {
        "eps_ttm": info.get("trailingEps"),
        "eps_forward": info.get("forwardEps"),
        "revenue_per_share": info.get("revenuePerShare"),
        "book_value_per_share": info.get("bookValue"),
        "dividend_yield": _raw_div_yield / 100 if _raw_div_yield is not None else None,
        "dividend_rate": info.get("dividendRate"),
        "payout_ratio": info.get("payoutRatio"),
    }

    # --- Growth ---
    growth = {
        "revenue_growth_yoy": info.get("revenueGrowth"),
        "earnings_growth_yoy": info.get("earningsGrowth"),
        "earnings_growth_quarterly": info.get("earningsQuarterlyGrowth"),
    }

    # --- Financial Health ---
    health = {
        "debt_to_equity": info.get("debtToEquity"),
        "total_debt": info.get("totalDebt"),
        "total_cash": info.get("totalCash"),
        "current_ratio": info.get("currentRatio"),
        "quick_ratio": info.get("quickRatio"),
        "interest_coverage": _safe_interest_coverage(t),
        "fcf": info.get("freeCashflow"),
        "operating_cash_flow": info.get("operatingCashflow"),
    }

    # --- Compute Graham Number ---
    eps = per_share["eps_ttm"]
    bvps = per_share["book_value_per_share"]
    if eps and bvps and eps > 0 and bvps > 0:
        valuation["graham_number"] = float(np.sqrt(22.5 * eps * bvps))
    else:
        valuation["graham_number"] = None

    # --- Financial Statements (last 5 years annual) ---
    statements = _fetch_statements(t)

    # --- Historical price data for sparklines ---
    hist = t.history(period="5y")
    trends = _compute_trends(hist, t)

    # --- News ---
    news = _fetch_news(t)

    return {
        "company": company,
        "market": market,
        "valuation": valuation,
        "profitability": profitability,
        "per_share": per_share,
        "growth": growth,
        "health": health,
        "statements": statements,
        "trends": trends,
        "news": news,
    }


def _safe_interest_coverage(t: yf.Ticker) -> Optional[float]:
    """Compute interest coverage from financial statements."""
    try:
        income = t.financials
        if income is not None and not income.empty:
            # Find EBIT or Operating Income row
            for label in income.index:
                if "EBIT" in str(label).upper() or "Operating Income" in str(label):
                    ebit = income.loc[label].iloc[0] if not income.empty else None
                    break
            else:
                ebit = None

            interest_expense = None
            for label in income.index:
                if "Interest Expense" in str(label):
                    interest_expense = abs(income.loc[label].iloc[0]) if not income.empty else None
                    break

            if ebit and interest_expense and interest_expense > 0:
                return float(ebit / interest_expense)
    except Exception:
        pass
    return None


def _fetch_statements(t: yf.Ticker) -> Dict[str, pd.DataFrame]:
    """Fetch annual financial statements, keeping last 5 years."""
    try:
        income = t.financials
        if income is not None:
            income = income.iloc[:, :5]  # last 5 years
    except Exception:
        income = pd.DataFrame()

    try:
        balance = t.balance_sheet
        if balance is not None:
            balance = balance.iloc[:, :5]
    except Exception:
        balance = pd.DataFrame()

    try:
        cashflow = t.cashflow
        if cashflow is not None:
            cashflow = cashflow.iloc[:, :5]
    except Exception:
        cashflow = pd.DataFrame()

    return {
        "income": income,
        "balance": balance,
        "cashflow": cashflow,
    }


def _compute_trends(hist: pd.DataFrame, t: yf.Ticker) -> Dict[str, list]:
    """Compute yearly trends for sparklines."""
    if hist.empty:
        return {"revenue": [], "profit": [], "debt": [], "price": []}

    # Price trend: yearly closes
    yearly = hist["Close"].resample("YE").last()
    price_trend = yearly.dropna().tolist()[-5:]

    # Revenue and profit from financials
    try:
        income = t.financials
        if income is not None and not income.empty:
            revenue_row = None
            net_income_row = None
            for label in income.index:
                l = str(label).strip()
                if "Total Revenue" == l or "Revenue" == l:
                    revenue_row = income.loc[label]
                if "Net Income" in l and "Common" in l:
                    net_income_row = income.loc[label]
                if "Net Income" == l and net_income_row is None:
                    net_income_row = income.loc[label]

            # Take last 5 years, reversed (oldest first for sparkline)
            if revenue_row is not None:
                revenue_trend = revenue_row.iloc[:5][::-1].dropna().tolist()
            else:
                revenue_trend = []

            if net_income_row is not None:
                profit_trend = net_income_row.iloc[:5][::-1].dropna().tolist()
            else:
                profit_trend = []
        else:
            revenue_trend = []
            profit_trend = []
    except Exception:
        revenue_trend = []
        profit_trend = []

    # Debt trend from balance sheet
    try:
        balance = t.balance_sheet
        if balance is not None and not balance.empty:
            debt_row = None
            for label in balance.index:
                if "Total Debt" in str(label) or "Long Term Debt" in str(label):
                    debt_row = balance.loc[label]
                    break
            if debt_row is not None:
                debt_trend = debt_row.iloc[:5][::-1].dropna().tolist()
            else:
                debt_trend = []
        else:
            debt_trend = []
    except Exception:
        debt_trend = []

    return {
        "revenue": revenue_trend,
        "profit": profit_trend,
        "debt": debt_trend,
        "price": price_trend,
    }


# ═══════════════════════════════════════════════════════════════
#  Peers
# ═══════════════════════════════════════════════════════════════

def fetch_peers(sector: str, industry: str, current_ticker: str) -> list[str]:
    """Get a list of peer tickers in the same sector/industry.

    Uses a curated mapping of common peer groups since yfinance
    doesn't directly expose peer lists.
    """
    # Curated peer groups for major sectors
    PEER_GROUPS = {
        "Semiconductors": ["NVDA", "AMD", "INTC", "QCOM", "AVGO", "TXN", "MU", "AMAT", "LRCX", "ADI"],
        "Software—Application": ["MSFT", "ORCL", "ADBE", "CRM", "NOW", "INTU", "WDAY", "SNOW", "DDOG"],
        "Software—Infrastructure": ["MSFT", "ORCL", "SNOW", "DDOG", "CRWD", "PANW", "SPLK", "MDB"],
        "Internet Content & Information": ["GOOGL", "META", "PINS", "SNAP", "TWTR"],
        "Internet Retail": ["AMZN", "EBAY", "ETSY", "W", "CHWY"],
        "Consumer Electronics": ["AAPL", "SONO", "GPRO", "SONY"],
        "Banks—Diversified": ["JPM", "BAC", "WFC", "C", "GS", "MS"],
        "Oil & Gas Integrated": ["XOM", "CVX", "BP", "SHEL", "TTE"],
        "Pharmaceuticals": ["PFE", "MRK", "JNJ", "LLY", "ABBV", "BMY", "GILD"],
        "Auto Manufacturers": ["TSLA", "F", "GM", "TM", "HMC", "RIVN", "LCID"],
        "Telecommunications": ["T", "VZ", "TMUS", "CMCSA"],
        "Aerospace & Defense": ["BA", "LMT", "RTX", "GD", "NOC"],
        "Healthcare Plans": ["UNH", "CI", "HUM", "CNC", "ELV"],
        "Credit Services": ["V", "MA", "AXP", "PYPL", "COF", "DFS"],
        "Restaurants": ["MCD", "SBUX", "CMG", "YUM", "DRI"],
        "Apparel Retail": ["TJX", "ROST", "BURL", "GPS"],
        "Home Improvement Retail": ["HD", "LOW"],
        "Discount Stores": ["WMT", "TGT", "COST", "DG", "DLTR"],
    }

    # Find matching peer group — exact match first, then substring fallback.
    # This avoids false matches like "Software—Application" matching "Software—Infrastructure".
    peers = []
    industry_lower = industry.lower()
    sector_lower = sector.lower()

    # Pass 1: exact match on industry or sector key
    for key, tickers in PEER_GROUPS.items():
        key_lower = key.lower()
        if key_lower == industry_lower or key_lower == sector_lower:
            peers = [t for t in tickers if t.upper() != current_ticker.upper()]
            break

    # Pass 2: substring match (industry first, since it's more specific)
    if not peers:
        for key, tickers in PEER_GROUPS.items():
            key_lower = key.lower()
            if key_lower in industry_lower or industry_lower in key_lower:
                peers = [t for t in tickers if t.upper() != current_ticker.upper()]
                break

    # Pass 3: sector-level fallback
    if not peers:
        for key, tickers in PEER_GROUPS.items():
            key_lower = key.lower()
            if key_lower in sector_lower or sector_lower in key_lower:
                peers = [t for t in tickers if t.upper() != current_ticker.upper()]
                break

    return peers[:6]  # cap at 6 peers


def fetch_peer_metrics(peer_tickers: list[str]) -> Dict[str, Dict[str, Any]]:
    """Fetch key metrics for a list of peer tickers.

    Uses _cached_ticker_info() so repeated peer lookups hit the cache
    instead of the API.
    """
    peer_data = {}
    for pt in peer_tickers:
        try:
            info = _cached_ticker_info(pt)
            if not info:
                continue
            _dy_raw = info.get("dividendYield")
            peer_data[pt] = {
                "name": info.get("shortName", pt),
                "pe_ttm": info.get("trailingPE"),
                "pe_forward": info.get("forwardPE"),
                "peg_ratio": info.get("pegRatio"),
                "pb_ratio": info.get("priceToBook"),
                "ps_ratio": info.get("priceToSalesTrailing12Months"),
                "ev_ebitda": info.get("enterpriseToEbitda"),
                "roe": info.get("returnOnEquity"),
                "roic": info.get("returnOnCapital"),
                "net_margin": info.get("profitMargins"),
                "revenue_growth": info.get("revenueGrowth"),
                "debt_to_equity": info.get("debtToEquity"),
                "beta": info.get("beta"),
                "market_cap": info.get("marketCap"),
                # Normalize: yfinance >=1.0 returns dividendYield as percentage
                "dividend_yield": _dy_raw / 100 if _dy_raw is not None else None,
            }
        except Exception:
            continue
    return peer_data


def compute_peer_averages(peer_data: Dict[str, Dict[str, Any]]) -> Dict[str, Optional[float]]:
    """Compute sector medians from peer data (median resists outlier distortion)."""
    averages = {}
    for key in peer_data[list(peer_data.keys())[0]].keys() if peer_data else []:
        if key in ("name",):
            continue
        values = [p[key] for p in peer_data.values() if p.get(key) is not None]
        averages[key] = float(np.median(values)) if values else None
    return averages


# ═══════════════════════════════════════════════════════════════
#  Quick health score
# ═══════════════════════════════════════════════════════════════

def compute_quick_health(info: dict) -> dict:
    """Compute a lightweight health score (0-10) from yfinance info ONLY.

    No financial statements required — uses info-level fields available in
    a single API call. Designed for batch sector scans where full F-Score
    computation would be too expensive.

    Returns dict with: score (0-10), verdict (Strong/Moderate/Weak)
    """
    score = 5  # baseline

    roe = info.get("returnOnEquity")
    if roe is not None:
        if roe > 0.20:
            score += 2
        elif roe > 0.15:
            score += 1
        elif roe < 0:
            score -= 1

    net_margin = info.get("profitMargins")
    if net_margin is not None:
        if net_margin > 0.15:
            score += 2
        elif net_margin > 0.05:
            score += 1
        elif net_margin < 0:
            score -= 1

    de = info.get("debtToEquity")
    if de is not None:
        if de < 50:
            score += 2
        elif de < 100:
            score += 1
        elif de > 200:
            score -= 1

    rev_growth = info.get("revenueGrowth")
    if rev_growth is not None:
        if rev_growth > 0.15:
            score += 1
        elif rev_growth < 0:
            score -= 1

    beta = info.get("beta")
    if beta is not None:
        if beta < 1.2:
            score += 1
        elif beta > 2.0:
            score -= 1

    score = max(0, min(10, score))

    if score >= 7:
        verdict = "Strong"
    elif score >= 4:
        verdict = "Moderate"
    else:
        verdict = "Weak"

    return {"score": score, "verdict": verdict}


# ═══════════════════════════════════════════════════════════════
#  Batch metrics (sector scans)
# ═══════════════════════════════════════════════════════════════

def fetch_batch_metrics(tickers: list[str], max_workers: int = 6) -> dict[str, Optional[dict]]:
    """Fetch key metrics for many tickers in parallel using ThreadPoolExecutor.

    This is a lighter fetch than fetch_company_data() — it only pulls info-level
    data (no financial statements, no news, no trends). Useful for batch scanning
    a sector or industry.

    Returns dict of ticker -> dict with:
        name, sector, industry, market_cap, price, pe_ttm, revenue_growth,
        quick_health (score + verdict), beta, net_margin, dividend_yield
    or None if the ticker failed.

    Uses 6 workers by default (down from 8) + rate-limiter waits so bursts
    stay within Yahoo's tolerance. The cached-info path means repeated
    scans are near-instant.
    """
    results = {}

    def _fetch_one(ticker: str) -> tuple[str, Optional[dict]]:
        try:
            info = _cached_ticker_info(ticker)
            if not info:
                return (ticker, None)
            qh = compute_quick_health(info)
            _dy_raw = info.get("dividendYield")
            return (ticker, {
                "name": info.get("longName") or info.get("shortName", ticker),
                "sector": info.get("sector", ""),
                "industry": info.get("industry", ""),
                "market_cap": info.get("marketCap"),
                "price": info.get("currentPrice") or info.get("regularMarketPrice"),
                "pe_ttm": info.get("trailingPE"),
                "revenue_growth": info.get("revenueGrowth"),
                "quick_health": qh,
                "beta": info.get("beta"),
                "net_margin": info.get("profitMargins"),
                "dividend_yield": _dy_raw / 100 if _dy_raw is not None else None,
            })
        except Exception:
            return (ticker, None)

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(_fetch_one, t): t for t in tickers}
        for future in as_completed(futures):
            t, data = future.result()
            if data is not None:
                results[t] = data

    return results


# ═══════════════════════════════════════════════════════════════
#  News
# ═══════════════════════════════════════════════════════════════

def _fetch_news(t: yf.Ticker) -> list[dict]:
    """Fetch recent news for a ticker from yfinance."""
    try:
        raw = t.news
        if not raw:
            return []
        news_items = []
        for item in raw[:8]:
            content = item.get("content") or {}

            # Safe URL extraction
            url = ""
            cu = content.get("canonicalUrl")
            if isinstance(cu, dict):
                url = cu.get("url", "")
            if not url:
                ctu = content.get("clickThroughUrl")
                if isinstance(ctu, dict):
                    url = ctu.get("url", "")

            # Safe publisher extraction
            publisher = ""
            provider = content.get("provider")
            if isinstance(provider, dict):
                publisher = provider.get("displayName", "")

            news_items.append({
                "title": content.get("title", ""),
                "summary": (content.get("summary") or "")[:150],
                "url": url,
                "publisher": publisher,
                "published": content.get("pubDate", ""),
            })
        return news_items
    except Exception:
        return []


# ═══════════════════════════════════════════════════════════════
#  Macro Context
# ═══════════════════════════════════════════════════════════════

def fetch_macro_context() -> Dict[str, Any]:
    """Fetch macro market context: VIX, S&P trend, yield curve, credit, dollar.

    Returns a dict of indicators, each with a value, verdict, and color.
    All errors are swallowed — individual indicators return None on failure.

    Rate-limiter waits between each indicator spread the cold-load burst
    of 6 API calls over ~3 seconds instead of <1 second.
    """
    macro = {}

    # ── VIX (Fear Gauge) ──────────────────────────────────
    try:
        vix = _get_macro_ticker("^VIX")
        _rate_limiter.wait()
        vix_info = _retry_with_backoff(lambda: vix.info or {})
        vix_price = vix_info.get("regularMarketPrice") or vix_info.get("currentPrice")
        if vix_price is not None:
            if vix_price < 15:
                vix_verdict = "Calm"
                vix_color = "#00C853"
            elif vix_price <= 25:
                vix_verdict = "Normal"
                vix_color = "#FFD600"
            else:
                vix_verdict = "Fearful"
                vix_color = "#FF1744"
            macro["vix"] = {
                "value": vix_price,
                "label": "Fear Gauge",
                "verdict": vix_verdict,
                "color": vix_color,
                "detail": f"VIX at {vix_price:.1f} — {vix_verdict.lower()} market",
            }
    except Exception:
        pass

    # ── S&P 500 Trend ────────────────────────────────────
    try:
        spx = _get_macro_ticker("^GSPC")
        _rate_limiter.wait()
        spx_info = _retry_with_backoff(lambda: spx.info or {})
        spx_price = spx_info.get("regularMarketPrice") or spx_info.get("currentPrice")
        spx_50ma = spx_info.get("fiftyDayAverage")
        spx_200ma = spx_info.get("twoHundredDayAverage")

        if spx_price and spx_50ma and spx_200ma:
            above_50 = spx_price > spx_50ma
            above_200 = spx_price > spx_200ma

            if above_50 and above_200:
                trend_verdict = "Uptrend"
                trend_color = "#00C853"
                trend_detail = "S&P above both 50-day and 200-day moving averages — bullish structure"
            elif above_200 and not above_50:
                trend_verdict = "Choppy"
                trend_color = "#FFD600"
                trend_detail = "S&P above 200-day but below 50-day — short-term weakness in a long-term uptrend"
            elif above_50 and not above_200:
                trend_verdict = "Choppy"
                trend_color = "#FFD600"
                trend_detail = "S&P above 50-day but below 200-day — recovering but long-term trend is still down"
            else:
                trend_verdict = "Downtrend"
                trend_color = "#FF1744"
                trend_detail = "S&P below both key moving averages — bearish structure"

            macro["sp500"] = {
                "value": spx_price,
                "label": "S&P 500",
                "verdict": trend_verdict,
                "color": trend_color,
                "detail": trend_detail,
            }
    except Exception:
        pass

    # ── Yield Curve (10Y - 13W) ──────────────────────────
    try:
        tnx = _get_macro_ticker("^TNX")
        _rate_limiter.wait()
        tnx_price = (_retry_with_backoff(lambda: tnx.info or {})).get("regularMarketPrice")

        irx = _get_macro_ticker("^IRX")
        _rate_limiter.wait()
        irx_price = (_retry_with_backoff(lambda: irx.info or {})).get("regularMarketPrice")

        if tnx_price is not None and irx_price is not None:
            spread = tnx_price - irx_price
            if spread > 1.0:
                curve_verdict = "Steep"
                curve_color = "#00C853"
                curve_detail = f"Yield curve is steep ({spread:.1f}%) — banks benefit, economy expanding"
            elif spread > 0:
                curve_verdict = "Flat"
                curve_color = "#FFD600"
                curve_detail = f"Yield curve is flat ({spread:.1f}%) — watch for inversion, often precedes slowdown"
            else:
                curve_verdict = "Inverted"
                curve_color = "#FF1744"
                curve_detail = f"Yield curve inverted ({spread:.1f}%) — historically a recession warning signal"

            macro["yield_curve"] = {
                "value": spread,
                "label": "Yield Curve",
                "verdict": curve_verdict,
                "color": curve_color,
                "detail": curve_detail,
            }
    except Exception:
        pass

    # ── Credit Health (HYG vs 52w high) ──────────────────
    try:
        hyg = _get_macro_ticker("HYG")
        _rate_limiter.wait()
        hyg_info = _retry_with_backoff(lambda: hyg.info or {})
        hyg_price = hyg_info.get("regularMarketPrice") or hyg_info.get("currentPrice")
        hyg_hi = hyg_info.get("fiftyTwoWeekHigh")

        if hyg_price and hyg_hi and hyg_hi > 0:
            pct_off_high = ((hyg_price - hyg_hi) / hyg_hi) * 100
            if pct_off_high > -3:
                credit_verdict = "Healthy"
                credit_color = "#00C853"
            elif pct_off_high > -8:
                credit_verdict = "Cautious"
                credit_color = "#FFD600"
            else:
                credit_verdict = "Stressed"
                credit_color = "#FF1744"

            macro["credit"] = {
                "value": hyg_price,
                "label": "Credit",
                "verdict": credit_verdict,
                "color": credit_color,
                "detail": f"HYG at {hyg_price:.1f} ({pct_off_high:.1f}% off 52w high) — high-yield bonds are {credit_verdict.lower()}",
            }
    except Exception:
        pass

    # ── Dollar (DXY) ─────────────────────────────────────
    try:
        dxy = _get_macro_ticker("DX-Y.NYB")
        _rate_limiter.wait()
        dxy_info = _retry_with_backoff(lambda: dxy.info or {})
        dxy_price = dxy_info.get("regularMarketPrice") or dxy_info.get("currentPrice")
        dxy_50ma = dxy_info.get("fiftyDayAverage")

        if dxy_price and dxy_50ma and dxy_50ma > 0:
            dxy_pct = ((dxy_price - dxy_50ma) / dxy_50ma) * 100
            if dxy_pct > 1:
                dollar_verdict = "Rising"
                dollar_color = "#00C853"
            elif dxy_pct >= -1:
                dollar_verdict = "Stable"
                dollar_color = "#FFD600"
            else:
                dollar_verdict = "Falling"
                dollar_color = "#FF1744"

            macro["dollar"] = {
                "value": dxy_price,
                "label": "Dollar",
                "verdict": dollar_verdict,
                "color": dollar_color,
                "detail": f"DXY at {dxy_price:.1f} — {dollar_verdict.lower()} vs 50-day average",
            }
    except Exception:
        pass

    return macro


# ═══════════════════════════════════════════════════════════════
#  Analyst Data
# ═══════════════════════════════════════════════════════════════

def fetch_analyst_data(ticker: str) -> Dict[str, Any]:
    """Fetch analyst price targets and recommendations for a ticker.

    Returns a dict with price_targets, recommendations, and a plain-English verdict.
    """
    try:
        t = _get_ticker(ticker.upper())
    except Exception:
        return {}

    result = {}

    # ── Price Targets ────────────────────────────────────
    try:
        pt = t.analyst_price_targets
        if isinstance(pt, dict) and pt:
            info = _cached_ticker_info(ticker)
            price = info.get("currentPrice") or info.get("regularMarketPrice")
            result["price_targets"] = {
                "current": price,
                "low": pt.get("low"),
                "mean": pt.get("mean"),
                "median": pt.get("median"),
                "high": pt.get("high"),
            }
            # Compute upside/downside
            target = pt.get("mean") or pt.get("median")
            if target and price and price > 0:
                upside_pct = ((target - price) / price) * 100
                result["price_targets"]["upside_pct"] = upside_pct
    except Exception:
        pass

    # ── Recommendations ──────────────────────────────────
    try:
        recs = t.recommendations
        if recs is not None and not recs.empty:
            latest = recs.iloc[0]
            rec_data = {
                "strongBuy": int(latest.get("strongBuy", 0)),
                "buy": int(latest.get("buy", 0)),
                "hold": int(latest.get("hold", 0)),
                "sell": int(latest.get("sell", 0)),
                "strongSell": int(latest.get("strongSell", 0)),
            }
            rec_data["total"] = sum(rec_data.values())
            rec_data["buys"] = rec_data["strongBuy"] + rec_data["buy"]
            rec_data["sells"] = rec_data["sell"] + rec_data["strongSell"]

            # Verdict
            buy_pct = rec_data["buys"] / rec_data["total"] if rec_data["total"] > 0 else 0

            if buy_pct >= 0.6:
                rec_data["verdict"] = "Bullish"
                rec_data["verdict_color"] = "#00C853"
            elif buy_pct >= 0.4:
                rec_data["verdict"] = "Neutral"
                rec_data["verdict_color"] = "#FFD600"
            else:
                rec_data["verdict"] = "Bearish"
                rec_data["verdict_color"] = "#FF1744"

            result["recommendations"] = rec_data
    except Exception:
        pass

    return result


# ═══════════════════════════════════════════════════════════════
#  Institutional Holders
# ═══════════════════════════════════════════════════════════════

def fetch_institutional_data(ticker: str) -> Dict[str, Any]:
    """Fetch top institutional holders for a ticker.

    Returns a list of holders with name, % held, and recent change.
    """
    try:
        t = _get_ticker(ticker.upper())
        holders = t.institutional_holders
        if holders is None or holders.empty:
            return {"holders": [], "verdict": None}
    except Exception:
        return {"holders": [], "verdict": None}

    try:
        top_holders = []
        net_change = 0
        count = 0

        for _, row in holders.head(10).iterrows():
            pct_change = row.get("pctChange", 0) or 0
            pct_held = row.get("pctHeld", 0) or 0
            holder_name = row.get("Holder", "Unknown")
            value = row.get("Value")

            top_holders.append({
                "name": str(holder_name),
                "pct_held": float(pct_held) if pct_held else None,
                "pct_change": float(pct_change) if pct_change else None,
                "value": float(value) if value and not pd.isna(value) else None,
            })
            if pct_change is not None:
                net_change += float(pct_change)
                count += 1

        # Verdict: are institutions net buying or selling?
        avg_change = net_change / count if count > 0 else 0
        if avg_change > 1:
            verdict = "Buying"
            verdict_color = "#00C853"
            verdict_text = "Institutions have been increasing their positions — a vote of confidence"
        elif avg_change >= -1:
            verdict = "Holding"
            verdict_color = "#FFD600"
            verdict_text = "Institutions are holding steady — no strong directional signal"
        else:
            verdict = "Selling"
            verdict_color = "#FF1744"
            verdict_text = "Institutions have been reducing positions — worth understanding why"

        return {
            "holders": top_holders[:5],
            "verdict": verdict,
            "verdict_color": verdict_color,
            "verdict_text": verdict_text,
        }
    except Exception:
        return {"holders": [], "verdict": None}


# ═══════════════════════════════════════════════════════════════
#  Top Movers
# ═══════════════════════════════════════════════════════════════

# Trimmed from ~80 to ~40 liquid US stocks — every name here is traded by
# recognition, covers what most users care about, and cuts API load in half.
_MOVERS_BASKET = [
    # Tech / Semis
    "AAPL", "MSFT", "NVDA", "AMD", "INTC", "AVGO", "CRM", "ADBE", "ORCL", "PLTR",
    # Internet / Comms
    "GOOGL", "META", "AMZN", "NFLX", "DIS", "UBER",
    # Financials
    "JPM", "BAC", "GS", "V", "AXP",
    # Healthcare
    "JNJ", "PFE", "MRK", "ABBV", "LLY", "UNH",
    # Energy
    "XOM", "CVX", "COP", "OXY",
    # Industrials
    "CAT", "GE", "BA", "LMT",
    # Consumer
    "WMT", "COST", "HD", "NKE", "SBUX", "MCD", "KO", "TSLA",
    # Materials / RE
    "FCX", "NEM",
]


def fetch_top_movers(basket: list[str] | None = None, top_n: int = 10,
                     max_workers: int = 4) -> list[dict]:
    """Fetch daily % changes for a basket of stocks and return the top N movers.

    Returns a list of dicts sorted by absolute daily change (largest first):
        ticker, name, price, change_pct, direction ("up"/"down"), volume

    Uses 4 workers (down from 12) + cached info so bursts are small and
    repeated calls are near-instant. Cold cache: ~20 s for 40 tickers.
    Warm cache: < 1 s.
    """
    tickers = basket or _MOVERS_BASKET

    def _fetch_change(ticker: str) -> Optional[dict]:
        try:
            info = _cached_ticker_info(ticker)
            if not info:
                return None
            price = info.get("currentPrice") or info.get("regularMarketPrice")
            prev_close = info.get("regularMarketPreviousClose") or info.get("previousClose")
            change_pct = info.get("regularMarketChangePercent")
            if change_pct is None and price and prev_close and prev_close > 0:
                change_pct = ((price - prev_close) / prev_close) * 100
            if price is None or change_pct is None:
                return None
            name = info.get("shortName") or info.get("longName", ticker)
            return {
                "ticker": ticker,
                "name": name,
                "price": price,
                "change_pct": round(change_pct, 2),
                "direction": "up" if change_pct >= 0 else "down",
                "volume": info.get("regularMarketVolume") or info.get("volume", 0),
            }
        except Exception:
            return None

    results = []
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(_fetch_change, t): t for t in tickers}
        for future in as_completed(futures):
            data = future.result()
            if data and abs(data["change_pct"]) > 0.01:
                results.append(data)

    # Sort by absolute change, biggest first
    results.sort(key=lambda x: abs(x["change_pct"]), reverse=True)
    return results[:top_n]


# ═══════════════════════════════════════════════════════════════
#  Market News
# ═══════════════════════════════════════════════════════════════

_MARKET_NEWS_TICKERS = ["SPY", "AAPL", "MSFT", "^GSPC"]


def fetch_market_news(max_items: int = 10) -> list[dict]:
    """Fetch aggregated market-wide news from major ticker news feeds.

    Fetches news for a few key tickers, deduplicates by title, and returns
    the most recent unique items.
    """
    all_news = []
    seen_titles = set()

    for ticker in _MARKET_NEWS_TICKERS:
        try:
            t = _get_ticker(ticker)
            items = _fetch_news(t)
            for item in items:
                title_key = item.get("title", "")[:80].lower()
                if title_key and title_key not in seen_titles:
                    seen_titles.add(title_key)
                    all_news.append(item)
        except Exception:
            continue

    # Sort by published date (most recent first)
    all_news.sort(key=lambda x: x.get("published", ""), reverse=True)
    return all_news[:max_items]


# ═══════════════════════════════════════════════════════════════
#  Market Indices
# ═══════════════════════════════════════════════════════════════

_INDICES_CONFIG = {
    "S&P 500": {"ticker": "^GSPC", "emoji": "📊"},
    "NASDAQ": {"ticker": "^IXIC", "emoji": "💻"},
    "DJIA": {"ticker": "^DJI", "emoji": "🏛️"},
    "NYSE Comp.": {"ticker": "^NYA", "emoji": "🏦"},
    "NASDAQ-100": {"ticker": "^NDX", "emoji": "🚀"},
    "S&P 400": {"ticker": "^MID", "emoji": "📈"},
    "Russell 2000": {"ticker": "^RUT", "emoji": "🏢"},
}


def fetch_market_indices() -> list[dict]:
    """Fetch current levels and daily changes for major US stock indices.

    Returns list of dicts: name, emoji, price, change_pct, direction

    Uses cached info so repeated calls are near-instant.
    """
    results = []

    for name, cfg in _INDICES_CONFIG.items():
        try:
            info = _cached_ticker_info(cfg["ticker"])
            if not info:
                continue
            price = info.get("currentPrice") or info.get("regularMarketPrice")
            prev_close = info.get("regularMarketPreviousClose") or info.get("previousClose")
            change_pct = info.get("regularMarketChangePercent")
            if change_pct is None and price and prev_close and prev_close > 0:
                change_pct = ((price - prev_close) / prev_close) * 100
            if price is None:
                continue
            results.append({
                "name": name,
                "emoji": cfg["emoji"],
                "ticker": cfg["ticker"],
                "price": price,
                "change_pct": round(change_pct, 2) if change_pct is not None else None,
                "direction": "up" if (change_pct or 0) >= 0 else "down",
            })
        except Exception:
            continue

    return results
