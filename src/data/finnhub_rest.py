"""
Finnhub REST API client for quick supplemental data.

Provides a lightweight wrapper around three Finnhub REST endpoints (quote,
profile2, basic-financials) with a 30s in-memory cache, rate-limit guard
(~55 calls/min soft cap), and graceful no-op when FINNHUB_API_KEY is unset.

Designed as a complement to the primary yfinance data layer — when Finnhub
data is available it's faster and free-tier-friendly; when it isn't (no key,
rate-limited, down), callers degrade to None and fall through to yfinance.

Usage:
    client = FinnhubRestClient()
    quote = client.get_quote("AAPL")   # {"c": 150.0, "d": 1.5, ...}
    profile = client.get_profile("AAPL")  # {"name": "Apple Inc", ...}
    financials = client.get_basic_financials("AAPL")  # {"pe": 28.5, ...}
"""

import logging
import os
import time
from typing import Dict, Optional, Tuple

import requests

_logger = logging.getLogger(__name__)

_FINNHUB_BASE_URL = "https://finnhub.io/api/v1"
_CACHE_TTL = 30  # seconds
_RATE_LIMIT_MAX = 55  # soft cap — return None when approaching 60/min
_RATE_LIMIT_WINDOW = 60  # seconds


class FinnhubRestClient:
    """Thin REST client for three Finnhub endpoints with caching and rate limiting.

    Every fetch method returns None when data is unavailable (no API key,
    rate-limited, HTTP error, or parse failure) so callers can always
    fall through to yfinance without extra branching.

    Attributes:
        _api_key: Finnhub API token (empty string = disabled).
        _cache: Dict mapping ``"{endpoint}:{TICKER}"`` to ``(timestamp, data)``.
        _call_timestamps: List of ``time.time()`` values for recent API calls.
        _no_key_warned: Whether the missing-key warning has been emitted.
    """

    def __init__(self, api_key: Optional[str] = None) -> None:
        """Initialize the client.

        Args:
            api_key: Finnhub API token. If None, read from the
                ``FINNHUB_API_KEY`` environment variable. When the key is
                empty or unset the client is permanently disabled — every
                fetch returns None.
        """
        key = api_key if api_key is not None else os.environ.get("FINNHUB_API_KEY", "")
        self._api_key: str = key.strip()

        self._cache: Dict[str, Tuple[float, dict]] = {}
        self._call_timestamps: list[float] = []
        self._no_key_warned: bool = False

    # ─── Public API ───────────────────────────────────────────────────

    def get_quote(self, ticker: str) -> Optional[dict]:
        """Fetch real-time quote snapshot for *ticker* from ``/quote``.

        Returns a dict with the seven standard Finnhub quote fields:
            c (current price), d (change), dp (change %),
            h (day high), l (day low), o (open), pc (previous close).

        Null/missing fields are omitted from the result so callers can
        safely use ``.get("c")`` without extra None-checking.
        """
        result = self._fetch("quote", ticker)
        if result is None:
            return None

        fields = {"c", "d", "dp", "h", "l", "o", "pc"}
        cleaned = {k: v for k, v in result.items() if k in fields and v is not None}
        return cleaned if cleaned else None

    def get_profile(self, ticker: str) -> Optional[dict]:
        """Fetch company profile from ``/stock/profile2``.

        Returns a dict with up to seven fields:
            name, sector, industry, logo, marketCap, shareOutstanding, employees.
        """
        result = self._fetch("stock/profile2", ticker)
        if result is None:
            return None

        fields = {"name", "sector", "industry", "logo", "marketCap",
                  "shareOutstanding", "employees"}
        cleaned = {k: v for k, v in result.items() if k in fields and v is not None}
        return cleaned if cleaned else None

    def get_basic_financials(self, ticker: str) -> Optional[dict]:
        """Fetch basic financial metrics from ``/stock/basic-financials``.

        Returns a dict with up to five fields extracted from the ``metric``
        sub-object:
            pe, epsAnnual, beta, dividendYield, pb.
        """
        result = self._fetch("stock/basic-financials", ticker)
        if result is None:
            return None

        metric = result.get("metric")
        if not isinstance(metric, dict):
            return None

        fields = {"pe", "epsAnnual", "beta", "dividendYield", "pb"}
        cleaned = {k: v for k, v in metric.items() if k in fields and v is not None}
        return cleaned if cleaned else None

    # ─── Internal: fetch + caching + rate-limit ───────────────────────

    def _fetch(self, endpoint: str, ticker: str) -> Optional[dict]:
        """Internal fetch with caching and rate-limit guard.

        Steps:
          1. If no API key is set, log a one-time warning and return None.
          2. Check the 30s in-memory cache.
          3. Check the rate-limit guard (>=55 calls in last 60s → None).
          4. Make the HTTP GET request.
          5. On 429, mark the rate limit as full and return None.
          6. On success, cache the result and return it.
          7. On any exception, log WARNING and return None.
        """
        # ── Step 1: API key check ──────────────────────────────────
        if not self._api_key:
            if not self._no_key_warned:
                _logger.warning(
                    "FINNHUB_API_KEY not set — Finnhub REST client disabled"
                )
                self._no_key_warned = True
            return None

        key = f"{endpoint}:{ticker.upper()}"

        # ── Step 2: Cache check ────────────────────────────────────
        cached = self._cache.get(key)
        if cached is not None:
            ts, data = cached
            if time.time() - ts < _CACHE_TTL:
                return data

        # ── Step 3: Rate-limit guard ───────────────────────────────
        self._prune_timestamps()
        if len(self._call_timestamps) >= _RATE_LIMIT_MAX:
            _logger.warning(
                "Finnhub rate-limit guard active (%d calls in last %ds) "
                "— returning None for %s:%s",
                len(self._call_timestamps),
                _RATE_LIMIT_WINDOW,
                endpoint,
                ticker.upper(),
            )
            return None

        # ── Step 4: HTTP request ───────────────────────────────────
        url = f"{_FINNHUB_BASE_URL}/{endpoint}?symbol={ticker}"
        try:
            resp = requests.get(url, params={"token": self._api_key}, timeout=10)
        except requests.RequestException as exc:
            _logger.warning(
                "Finnhub HTTP error for %s:%s — %s",
                endpoint,
                ticker.upper(),
                exc,
            )
            return None

        # ── Step 5: 429 handling ───────────────────────────────────
        if resp.status_code == 429:
            _logger.warning(
                "Finnhub rate-limited (429) on %s:%s",
                endpoint,
                ticker.upper(),
            )
            # Saturate the timestamp window so subsequent calls also get
            # blocked for a while.
            now = time.time()
            self._call_timestamps = [now] * _RATE_LIMIT_MAX
            return None

        # ── Step 6: Non-200 handling ───────────────────────────────
        if not resp.ok:
            _logger.warning(
                "Finnhub returned %d for %s:%s",
                resp.status_code,
                endpoint,
                ticker.upper(),
            )
            return None

        # ── Step 7: Parse JSON ─────────────────────────────────────
        try:
            data = resp.json()
        except ValueError as exc:
            _logger.warning(
                "Finnhub JSON parse error for %s:%s — %s",
                endpoint,
                ticker.upper(),
                exc,
            )
            return None

        if not isinstance(data, dict):
            _logger.warning(
                "Finnhub returned unexpected type for %s:%s — %s",
                endpoint,
                ticker.upper(),
                type(data).__name__,
            )
            return None

        # ── Cache and return ───────────────────────────────────────
        now = time.time()
        self._cache[key] = (now, data)
        self._call_timestamps.append(now)

        return data

    def _prune_timestamps(self) -> None:
        """Remove call timestamps older than the rate-limit window."""
        cutoff = time.time() - _RATE_LIMIT_WINDOW
        self._call_timestamps = [
            t for t in self._call_timestamps if t > cutoff
        ]
