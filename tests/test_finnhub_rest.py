"""Tests for FinnhubRestClient — caching, rate-limiting, parsing, and merge."""

import time
from unittest.mock import MagicMock, patch

from src.data.finnhub_rest import FinnhubRestClient


class TestFinnhubRestClient:
    """FinnhubRestClient: caching, rate-limiting, parsing, and data enrichment."""

    # ── Helpers ──────────────────────────────────────────────────────────

    @staticmethod
    def _mock_response(json_data, ok=True, status_code=200):
        """Build a mock ``requests.Response`` with inline JSON."""
        mock_resp = MagicMock()
        mock_resp.ok = ok
        mock_resp.status_code = status_code
        mock_resp.json.return_value = json_data
        return mock_resp

    # ── Parsing ─────────────────────────────────────────────────────────

    def test_get_quote_parsing(self):
        """Valid quote JSON is cleaned to the seven standard fields."""
        client = FinnhubRestClient(api_key="test-key")
        mock_resp = self._mock_response({
            "c": 150.25, "d": 1.50, "dp": 1.01,
            "h": 151.00, "l": 149.00, "o": 149.50, "pc": 148.75,
            "extra_field": "should_be_ignored",
        })

        with patch("requests.get", return_value=mock_resp):
            result = client.get_quote("AAPL")

        assert result is not None
        assert result["c"] == 150.25
        assert result["d"] == 1.50
        assert result["dp"] == 1.01
        assert result["h"] == 151.00
        assert result["l"] == 149.00
        assert result["o"] == 149.50
        assert result["pc"] == 148.75
        assert "extra_field" not in result
        assert len(result) == 7

    def test_get_profile_parsing(self):
        """Valid profile2 JSON is cleaned to the expected fields."""
        client = FinnhubRestClient(api_key="test-key")
        mock_resp = self._mock_response({
            "name": "Apple Inc",
            "sector": "Technology",
            "industry": "Consumer Electronics",
            "logo": "https://example.com/logo.png",
            "marketCap": 2_800_000_000_000,
            "shareOutstanding": 15_500_000_000,
            "employees": 164_000,
            "extra_field": "ignored",
        })

        with patch("requests.get", return_value=mock_resp):
            result = client.get_profile("AAPL")

        assert result is not None
        assert result["name"] == "Apple Inc"
        assert result["sector"] == "Technology"
        assert result["industry"] == "Consumer Electronics"
        assert result["logo"] == "https://example.com/logo.png"
        assert result["marketCap"] == 2_800_000_000_000
        assert result["shareOutstanding"] == 15_500_000_000
        assert result["employees"] == 164_000
        assert "extra_field" not in result
        assert len(result) == 7

    def test_get_basic_financials_parsing(self):
        """Valid basic-financials JSON extracts the ``metric`` sub-object."""
        client = FinnhubRestClient(api_key="test-key")
        mock_resp = self._mock_response({
            "metric": {
                "pe": 28.5, "epsAnnual": 6.12, "beta": 1.25,
                "dividendYield": 0.005, "pb": 45.2,
            }
        })

        with patch("requests.get", return_value=mock_resp):
            result = client.get_basic_financials("AAPL")

        assert result is not None
        assert result["pe"] == 28.5
        assert result["epsAnnual"] == 6.12
        assert result["beta"] == 1.25
        assert result["dividendYield"] == 0.005
        assert result["pb"] == 45.2

        # Missing/malformed metric → None (use different tickers to avoid cache)
        bad_resp = self._mock_response({"metric": None})
        with patch("requests.get", return_value=bad_resp):
            assert client.get_basic_financials("MSFT") is None

        no_metric = self._mock_response({})
        with patch("requests.get", return_value=no_metric):
            assert client.get_basic_financials("GOOGL") is None

    # ── Caching ─────────────────────────────────────────────────────────

    def test_cache_hit(self):
        """Second call for same ticker within 30s returns cached value.

        Different tickers have independent cache entries.
        """
        client = FinnhubRestClient(api_key="test-key")

        aapl_resp = self._mock_response({"c": 150.0, "d": 1.0})
        msft_resp = self._mock_response({"c": 400.0, "d": 2.0})

        with patch("requests.get", side_effect=[aapl_resp, msft_resp]) as mock_get:
            # First call for each ticker — two API calls
            r1 = client.get_quote("AAPL")
            r2 = client.get_quote("MSFT")
            assert r1["c"] == 150.0
            assert r2["c"] == 400.0
            assert mock_get.call_count == 2

            # Second calls — both cached, zero additional API calls
            r3 = client.get_quote("AAPL")
            r4 = client.get_quote("MSFT")
            assert r3["c"] == 150.0
            assert r4["c"] == 400.0
            assert mock_get.call_count == 2

    def test_cache_expiry(self):
        """Cache entry older than 30s triggers a fresh fetch."""
        client = FinnhubRestClient(api_key="test-key")

        # Insert a stale cache entry (31 seconds old)
        old_ts = time.time() - 31
        client._cache["quote:AAPL"] = (old_ts, {"c": 150.0})

        fresh_resp = self._mock_response({"c": 155.0})
        with patch("requests.get", return_value=fresh_resp) as mock_get:
            result = client.get_quote("AAPL")
            assert result["c"] == 155.0  # fresh value from API
            mock_get.assert_called_once()

    # ── Rate limiting ───────────────────────────────────────────────────

    def test_rate_limit_tracking(self):
        """55+ calls in the 60s window returns None.

        A 429 response also saturates the timestamp window.
        """
        client = FinnhubRestClient(api_key="test-key")
        now = time.time()
        client._call_timestamps = [now] * 55

        with patch("requests.get") as mock_get:
            result = client.get_quote("AAPL")
            assert result is None
            mock_get.assert_not_called()

        # 429 response saturates the window
        client2 = FinnhubRestClient(api_key="test-key")
        mock_429 = MagicMock()
        mock_429.status_code = 429
        mock_429.ok = False

        with patch("requests.get", return_value=mock_429):
            result = client2.get_quote("AAPL")
            assert result is None
            assert len(client2._call_timestamps) == 55

    # ── Error handling ──────────────────────────────────────────────────

    def test_no_api_key(self):
        """Without an API key, every fetch returns None and HTTP is never called."""
        # Explicit empty key
        client = FinnhubRestClient(api_key="")
        with patch("requests.get") as mock_get:
            assert client.get_quote("AAPL") is None
            assert client.get_profile("AAPL") is None
            assert client.get_basic_financials("AAPL") is None
            mock_get.assert_not_called()

        # Implicit via constructor's env fallback
        with patch.object(FinnhubRestClient.__init__, "__defaults__", None):
            pass  # not needed — rely on explicit-key test above

    def test_malformed_response(self):
        """Non-dict JSON, parse errors, and HTTP errors all return None."""
        client = FinnhubRestClient(api_key="test-key")

        # Non-dict JSON (list instead of dict)
        with patch("requests.get", return_value=self._mock_response(["not", "a", "dict"])):
            assert client.get_quote("AAPL") is None

        # JSON parse error
        bad_json = MagicMock()
        bad_json.ok = True
        bad_json.status_code = 200
        bad_json.json.side_effect = ValueError("bad json")
        with patch("requests.get", return_value=bad_json):
            assert client.get_quote("AAPL") is None

        # HTTP 500
        server_error = MagicMock()
        server_error.ok = False
        server_error.status_code = 500
        with patch("requests.get", return_value=server_error):
            assert client.get_quote("AAPL") is None

    # ── Data enrichment integration ─────────────────────────────────────

    def test_enrich_merges_correctly(self):
        """_apply_finnhub_data overwrites mapped fields from all three endpoints."""
        from src.data.fetcher import _apply_finnhub_data

        mock_client = MagicMock()
        mock_client.get_quote.return_value = {
            "c": 155.0, "d": 2.5, "dp": 1.65,
            "h": 156.0, "l": 153.0, "o": 154.0, "pc": 152.5,
        }
        mock_client.get_profile.return_value = {
            "name": "Apple Inc.",
            "sector": "Technology",
            "industry": "Consumer Electronics",
            "employees": 164_000,
            "beta": 1.25,
            "marketCap": 2_800_000_000_000,
            "shareOutstanding": 15_500_000_000,
        }
        mock_client.get_basic_financials.return_value = {
            "pe": 30.5, "epsAnnual": 6.50, "pb": 45.0,
        }

        sample_data = {
            "company": {
                "name": "Old Name", "sector": "Old Sector",
                "industry": "Old Industry", "employees": 100_000,
                "website": "https://example.com",
            },
            "market": {
                "price": 150.0, "previous_close": 149.0,
                "change": 1.0, "change_pct": 0.67,
                "day_high": 151.0, "day_low": 148.0, "open": 149.5,
                "market_cap": 2_500_000_000_000,
                "shares_outstanding": 16_000_000_000,
                "beta": 1.20, "employees": 100_000,
                "avg_volume": 50_000_000,
            },
            "valuation": {
                "pe_ttm": 28.0, "eps_ttm": 5.80,
                "pb_ratio": 40.0, "pe_forward": 25.0,
            },
            "per_share": {
                "eps_ttm": 5.80, "dividend_yield": 0.005,
                "book_value_per_share": 30.0,
            },
        }

        with patch("src.data.fetcher._get_finnhub_client", return_value=mock_client):
            result = _apply_finnhub_data(sample_data, "AAPL")

        # ── Quote → market ──
        assert result["market"]["price"] == 155.0
        assert result["market"]["previous_close"] == 152.5
        assert result["market"]["change"] == 2.5
        assert result["market"]["change_pct"] == 1.65
        assert result["market"]["day_high"] == 156.0
        assert result["market"]["day_low"] == 153.0
        assert result["market"]["open"] == 154.0

        # ── Profile → company ──
        assert result["company"]["name"] == "Apple Inc."
        assert result["company"]["sector"] == "Technology"
        assert result["company"]["industry"] == "Consumer Electronics"

        # ── Profile → market ──
        assert result["market"]["market_cap"] == 2_800_000_000_000
        assert result["market"]["shares_outstanding"] == 15_500_000_000
        assert result["market"]["beta"] == 1.25
        assert result["market"]["employees"] == 164_000

        # ── Financials → valuation ──
        assert result["valuation"]["pe_ttm"] == 30.5
        assert result["valuation"]["eps_ttm"] == 6.50
        assert result["valuation"]["pb_ratio"] == 45.0

        # ── Financials → per_share ──
        assert result["per_share"]["eps_ttm"] == 6.50

        # ── Non-mapped fields unchanged ──
        assert result["company"]["website"] == "https://example.com"
        assert result["market"]["avg_volume"] == 50_000_000
        assert result["valuation"]["pe_forward"] == 25.0
        assert result["per_share"]["dividend_yield"] == 0.005
        assert result["per_share"]["book_value_per_share"] == 30.0

    def test_enrich_no_overwrite_on_none(self):
        """None / missing Finnhub values do not overwrite existing data."""
        from src.data.fetcher import _apply_finnhub_data

        mock_client = MagicMock()
        # quote only provides "c"; the rest are missing
        mock_client.get_quote.return_value = {"c": 155.0}
        # profile only provides name
        mock_client.get_profile.return_value = {"name": "Apple Inc."}
        # financials completely unavailable
        mock_client.get_basic_financials.return_value = None

        sample_data = {
            "company": {
                "name": "Old Name", "sector": "Old Sector",
                "industry": "Old Industry",
            },
            "market": {
                "price": 150.0, "previous_close": 149.0,
                "change": 1.0, "change_pct": 0.67,
                "day_high": 151.0, "day_low": 148.0, "open": 149.5,
            },
            "valuation": {"pe_ttm": 28.0, "eps_ttm": 5.8, "pb_ratio": 40.0},
            "per_share": {"eps_ttm": 5.8},
        }

        with patch("src.data.fetcher._get_finnhub_client", return_value=mock_client):
            result = _apply_finnhub_data(sample_data, "AAPL")

        # price IS overwritten by quote.c
        assert result["market"]["price"] == 155.0

        # Fields missing from Finnhub quote are preserved
        assert result["market"]["previous_close"] == 149.0
        assert result["market"]["change"] == 1.0
        assert result["market"]["change_pct"] == 0.67
        assert result["market"]["day_high"] == 151.0
        assert result["market"]["day_low"] == 148.0
        assert result["market"]["open"] == 149.5

        # profile.name overwrites, but sector/industry (missing from Finnhub) preserved
        assert result["company"]["name"] == "Apple Inc."
        assert result["company"]["sector"] == "Old Sector"
        assert result["company"]["industry"] == "Old Industry"

        # financials was None → valuation untouched
        assert result["valuation"]["pe_ttm"] == 28.0
        assert result["valuation"]["eps_ttm"] == 5.8
        assert result["valuation"]["pb_ratio"] == 40.0

        # per_share untouched
        assert result["per_share"]["eps_ttm"] == 5.8
