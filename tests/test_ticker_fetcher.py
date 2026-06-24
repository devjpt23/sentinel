"""Tests for TickerDataFetcher — caching, backoff, parallel fetch."""

from unittest.mock import patch, MagicMock

import pandas as pd

from src.data.ticker_fetcher import TickerDataFetcher


class TestTickerDataFetcher:
    """Must cache per-cycle, backoff on 429, and handle empty sets."""

    def test_empty_fetch_returns_empty(self):
        fetcher = TickerDataFetcher(max_workers=2)
        result = fetcher.fetch_many(set())
        assert result == {}

    def test_per_cycle_cache(self):
        """Second call for same ticker within same cycle must hit cache."""
        fetcher = TickerDataFetcher(max_workers=2)
        # Fill cycle cache directly
        fetcher._cycle_cache["NVDA"] = {
            "ticker": "NVDA",
            "market": {"price": 150.0},
            "history": pd.DataFrame(),
        }
        # fetch_many should return cached data without calling yfinance
        with patch.object(fetcher, "_fetch_one") as mock_fetch:
            result = fetcher.fetch_many({"NVDA"})
            assert result["NVDA"]["market"]["price"] == 150.0
            mock_fetch.assert_not_called()

    def test_clear_cycle_cache(self):
        fetcher = TickerDataFetcher(max_workers=2)
        fetcher._cycle_cache["NVDA"] = {"ticker": "NVDA", "market": {}, "history": pd.DataFrame()}
        fetcher.clear_cycle()
        assert fetcher._cycle_cache == {}

    def test_backoff_on_429(self):
        """_fetch_one enters backoff when yfinance returns 429."""
        fetcher = TickerDataFetcher(max_workers=2)
        with patch("yfinance.Ticker") as mock_ticker_cls:
            mock_ticker_cls.side_effect = Exception("429 Too Many Requests")
            result = fetcher._fetch_one("NVDA")
            assert result is None
            assert "NVDA" in fetcher._backoff

    def test_backoff_ticker_skipped(self):
        """Ticker in backoff should be skipped without calling yfinance."""
        fetcher = TickerDataFetcher(max_workers=2)
        fetcher._backoff["NVDA"] = 9999999999.0  # Far future

        with patch.object(fetcher, "_fetch_one") as mock_fetch:
            result = fetcher.fetch_many({"NVDA"})
            assert result == {}
            mock_fetch.assert_not_called()

    def test_backoff_expired_retried(self):
        """Ticker past its backoff window should be fetched again."""
        fetcher = TickerDataFetcher(max_workers=2)
        import time
        fetcher._backoff["NVDA"] = time.time() - 10  # Expired

        with patch.object(fetcher, "_fetch_one") as mock_fetch:
            mock_fetch.return_value = {
                "ticker": "NVDA",
                "market": {"price": 150.0},
                "history": pd.DataFrame(),
            }
            result = fetcher.fetch_many({"NVDA"})
            assert "NVDA" in result
            mock_fetch.assert_called_once_with("NVDA")

    def test_mixed_cache_and_fetch(self):
        """Cached tickers should not block uncached ones from being fetched."""
        fetcher = TickerDataFetcher(max_workers=2)
        fetcher._cycle_cache["AAPL"] = {"ticker": "AAPL", "market": {}, "history": pd.DataFrame()}

        with patch.object(fetcher, "_fetch_one") as mock_fetch:
            mock_fetch.return_value = {
                "ticker": "NVDA",
                "market": {"price": 150.0},
                "history": pd.DataFrame(),
            }
            result = fetcher.fetch_many({"AAPL", "NVDA"})
            assert "AAPL" in result  # from cache
            assert "NVDA" in result  # from fetch
            mock_fetch.assert_called_once_with("NVDA")

    def test_fetch_one_success(self):
        """_fetch_one should extract price and history correctly."""
        mock_ticker = MagicMock()
        mock_ticker.info = {"currentPrice": 150.0, "averageVolume": 50000000}
        mock_ticker.history.return_value = pd.DataFrame(
            {"Close": [100, 101, 102]},
            index=pd.date_range(end="2024-01-15", periods=3, freq="D"),
        )

        with patch("yfinance.Ticker", return_value=mock_ticker):
            fetcher = TickerDataFetcher(max_workers=1)
            result = fetcher._fetch_one("NVDA")
            assert result is not None
            assert result["market"]["price"] == 150.0
            assert result["ticker"] == "NVDA"
