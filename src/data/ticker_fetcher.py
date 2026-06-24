"""Rate-limited parallel yfinance fetcher for reconciliation ticks.

Groups requests by ticker so N users watching the same ticker trigger
one yfinance call instead of N calls. Caps concurrent fetches, backs
off on 429, and caches results per reconciliation cycle.
"""

import time
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, List, Optional, Set

import pandas as pd
import yfinance as yf

logger = logging.getLogger(__name__)


class TickerDataFetcher:
    """Fetches lightweight market data for reconciliation ticks.

    One yfinance call per ticker regardless of how many users watch it.
    Uses ``ThreadPoolExecutor`` with a configurable concurrency cap.
    Tickers that return 429 are backed off for 5 minutes.
    """

    def __init__(self, max_workers: int = 5) -> None:
        self._max_workers = max_workers
        # Cycle cache: cleared at the start of each reconciliation tick
        self._cycle_cache: Dict[str, Dict] = {}
        # Backoff: ticker -> unix timestamp when backoff expires
        self._backoff: Dict[str, float] = {}

    def clear_cycle(self) -> None:
        """Clear the per-cycle cache. Call at the start of each tick."""
        self._cycle_cache.clear()

    def fetch_many(self, tickers: Set[str]) -> Dict[str, Dict]:
        """Fetch market data for *tickers* in parallel.

        Skips tickers currently in backoff. Returns a dict of
        ``{ticker: data_dict}`` for successful fetches only.
        """
        # Filter out backoff tickers
        now = time.time()
        to_fetch = {
            t for t in tickers
            if t not in self._backoff or now >= self._backoff[t]
        }
        if not to_fetch:
            return {}

        # Check cycle cache first
        remaining = {
            t for t in to_fetch if t not in self._cycle_cache
        }
        results = {
            t: self._cycle_cache[t] for t in to_fetch if t in self._cycle_cache
        }
        if not remaining:
            return results

        with ThreadPoolExecutor(max_workers=self._max_workers) as pool:
            futures = {pool.submit(self._fetch_one, t): t for t in remaining}
            for future in as_completed(futures):
                ticker = futures[future]
                try:
                    data = future.result()
                    if data:
                        results[ticker] = data
                        self._cycle_cache[ticker] = data
                except Exception:
                    logger.warning("fetch_many: failed for %s", ticker, exc_info=True)

        return results

    def _fetch_one(self, ticker: str) -> Optional[Dict]:
        """Fetch price + OHLCV history for one ticker."""
        try:
            t = yf.Ticker(ticker)
            try:
                info = t.info or {}
            except Exception:
                info = {}
            history = t.history(period="6mo")
            return {
                "ticker": ticker,
                "market": {
                    "price": info.get("currentPrice")
                              or info.get("regularMarketPrice"),
                    "avg_volume": info.get("averageVolume"),
                    "52w_high": info.get("fiftyTwoWeekHigh"),
                    "52w_low": info.get("fiftyTwoWeekLow"),
                },
                "history": history if history is not None and not history.empty
                           else pd.DataFrame(),
            }
        except Exception as exc:
            err = str(exc).lower()
            if "429" in err or "rate limit" in err:
                self._backoff[ticker] = time.time() + 300
                logger.warning(
                    "Rate limited on %s, backoff 5 min", ticker
                )
            return None
