"""Tests for the Alpaca options data endpoint and _options_data helper."""

import os
import json
from unittest.mock import patch, MagicMock

# Must be set before importing server (it checks at import time)
os.environ.setdefault("SENTINEL_API_KEY", "test-key")
os.environ.setdefault("ALPACA_API_KEY", "pk_test123")
os.environ.setdefault("ALPACA_SECRET_KEY", "sk_test456")

import pytest
from src.api.server import app, _options_data, _options_cache, _options_cache_lock


# ─── Fixtures ─────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def clear_options_cache():
    """Clear the options cache before each test."""
    with _options_cache_lock:
        _options_cache.clear()
    yield


@pytest.fixture
def client():
    app.config["TESTING"] = True
    with app.test_client() as client:
        yield client


def _headers():
    return {"X-API-Key": os.environ.get("SENTINEL_API_KEY", "test-key")}


def _options_get(client, url):
    """Helper: GET with API key header."""
    return client.get(url, headers=_headers())


# ─── Mock Data ────────────────────────────────────────────────────

MOCK_CONTRACTS_RESPONSE = {
    "option_contracts": [
        {
            "id": "AAPL240712C00180000",
            "symbol": "AAPL240712C00180000",
            "underlying_symbols": ["AAPL"],
            "type": "call",
            "strike_price": "180.0",
            "expiration_date": "2026-07-10",
            "exercise_style": "american",
        },
        {
            "id": "AAPL240712C00185000",
            "symbol": "AAPL240712C00185000",
            "underlying_symbols": ["AAPL"],
            "type": "call",
            "strike_price": "185.0",
            "expiration_date": "2026-07-10",
            "exercise_style": "american",
        },
        {
            "id": "AAPL240712P00180000",
            "symbol": "AAPL240712P00180000",
            "underlying_symbols": ["AAPL"],
            "type": "put",
            "strike_price": "180.0",
            "expiration_date": "2026-07-10",
            "exercise_style": "american",
        },
        {
            "id": "AAPL240712P00185000",
            "symbol": "AAPL240712P00185000",
            "underlying_symbols": ["AAPL"],
            "type": "put",
            "strike_price": "185.0",
            "expiration_date": "2026-07-10",
            "exercise_style": "american",
        },
        {
            "id": "AAPL240719C00180000",
            "symbol": "AAPL240719C00180000",
            "underlying_symbols": ["AAPL"],
            "type": "call",
            "strike_price": "180.0",
            "expiration_date": "2026-07-17",
            "exercise_style": "american",
        },
        {
            "id": "AAPL240719P00180000",
            "symbol": "AAPL240719P00180000",
            "underlying_symbols": ["AAPL"],
            "type": "put",
            "strike_price": "180.0",
            "expiration_date": "2026-07-17",
            "exercise_style": "american",
        },
    ]
}

MOCK_STOCK_PRICE_RESPONSE = {"trade": {"p": 185.50}}

MOCK_SNAPSHOTS_RESPONSE = {
    "snapshots": {
        "AAPL240712C00180000": {
            "latestTrade": {"p": 6.50, "s": 100, "t": "2026-07-10T14:30:00Z", "sz": "100"},
            "latestQuote": {"bp": 6.40, "ap": 6.60},
            "Greeks": {"delta": 0.65, "gamma": 0.045, "theta": -0.08, "vega": 0.15, "rho": 0.02},
            "impliedVolatility": 0.25,
        },
        "AAPL240712C00185000": {
            "latestTrade": {"p": 2.50, "s": 100},
            "latestQuote": {"bp": 2.40, "ap": 2.60},
            "Greeks": {"delta": 0.52, "gamma": 0.060, "theta": -0.10, "vega": 0.12, "rho": 0.01},
            "impliedVolatility": 0.28,
        },
        "AAPL240712P00180000": {
            "latestTrade": {"p": 1.50, "s": 100},
            "latestQuote": {"bp": 1.40, "ap": 1.60},
            "Greeks": {"delta": -0.35, "gamma": 0.045, "theta": -0.05, "vega": 0.10, "rho": -0.01},
            "impliedVolatility": 0.22,
        },
        "AAPL240712P00185000": {
            "latestTrade": {"p": 3.50, "s": 100},
            "latestQuote": {"bp": 3.40, "ap": 3.60},
            "Greeks": {"delta": -0.48, "gamma": 0.060, "theta": -0.07, "vega": 0.12, "rho": -0.02},
            "impliedVolatility": 0.30,
        },
        "AAPL240719C00180000": {
            "latestTrade": {"p": 8.00, "s": 100},
            "latestQuote": {"bp": 7.85, "ap": 8.15},
            "Greeks": {"delta": 0.60, "gamma": 0.040, "theta": -0.09, "vega": 0.18, "rho": 0.03},
            "impliedVolatility": 0.27,
        },
        "AAPL240719P00180000": {
            "latestTrade": {"p": 2.00, "s": 100},
            "latestQuote": {"bp": 1.90, "ap": 2.10},
            "Greeks": {"delta": -0.30, "gamma": 0.040, "theta": -0.06, "vega": 0.11, "rho": -0.01},
            "impliedVolatility": 0.24,
        },
    }
}

MOCK_YF_CHAIN_CALLS = MagicMock()
MOCK_YF_CHAIN_CALLS.iterrows.return_value = [
    (0, {"strike": 180.0, "openInterest": 45000, "volume": 12500, "impliedVolatility": 0.24}),
    (1, {"strike": 185.0, "openInterest": 30000, "volume": 8000, "impliedVolatility": 0.27}),
]

MOCK_YF_CHAIN_PUTS = MagicMock()
MOCK_YF_CHAIN_PUTS.iterrows.return_value = [
    (0, {"strike": 180.0, "openInterest": 55000, "volume": 10000, "impliedVolatility": 0.23}),
    (1, {"strike": 185.0, "openInterest": 60000, "volume": 12000, "impliedVolatility": 0.29}),
]


def _make_stock_resp(price=185.50, status_code=200):
    """Create a mock stock price response."""
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = {"trade": {"p": price}} if status_code == 200 else {}
    return resp


# ─── Tests for _options_data helper ───────────────────────────────

class TestOptionsData:
    """Tests for the _options_data data-fetching and merging logic."""

    @patch("src.api.server.requests.get")
    @patch("yfinance.Ticker")
    def test_successful_fetch_returns_full_shape(self, mock_yf, mock_get):
        """Happy path: Alpaca returns contracts + snapshots, yfinance supplements OI/vol."""
        # Configure mock responses
        contracts_resp = MagicMock()
        contracts_resp.status_code = 200
        contracts_resp.json.return_value = MOCK_CONTRACTS_RESPONSE

        snapshots_resp = MagicMock()
        snapshots_resp.status_code = 200
        snapshots_resp.json.return_value = MOCK_SNAPSHOTS_RESPONSE

        mock_get.side_effect = [contracts_resp, snapshots_resp, _make_stock_resp()]

        # Mock yfinance
        mock_ticker = MagicMock()
        mock_yf.return_value = mock_ticker
        mock_chain = MagicMock()
        mock_chain.calls = MOCK_YF_CHAIN_CALLS
        mock_chain.puts = MOCK_YF_CHAIN_PUTS
        mock_ticker.option_chain.return_value = mock_chain

        result, err = _options_data("AAPL")

        assert err is None
        assert result is not None

        # Top-level shape
        assert result["ticker"] == "AAPL"
        assert result["underlying_price"] == 185.50
        assert "summary" in result
        assert "expirations" in result
        assert "chain" in result

        # Expirations sorted
        assert result["expirations"] == ["2026-07-10", "2026-07-17"]

        # Chain shape — each expiry has calls and puts
        for expiry in result["expirations"]:
            assert "calls" in result["chain"][expiry]
            assert "puts" in result["chain"][expiry]

        # Contract data is populated
        july10 = result["chain"]["2026-07-10"]
        assert len(july10["calls"]) == 2
        assert len(july10["puts"]) == 2

        # Verify Greeks and pricing data
        call_180 = [c for c in july10["calls"] if c["strike"] == 180.0][0]
        assert call_180["last_price"] == 6.50
        assert call_180["bid"] == 6.40
        assert call_180["ask"] == 6.60
        assert call_180["delta"] == 0.65
        assert call_180["gamma"] == 0.045

    @patch("src.api.server.requests.get")
    @patch("yfinance.Ticker")
    def test_yfinance_oi_and_volume_merged(self, mock_yf, mock_get):
        """yfinance OI/volume data is merged into contracts."""
        contracts_resp = MagicMock()
        contracts_resp.status_code = 200
        contracts_resp.json.return_value = MOCK_CONTRACTS_RESPONSE

        snapshots_resp = MagicMock()
        snapshots_resp.status_code = 200
        snapshots_resp.json.return_value = MOCK_SNAPSHOTS_RESPONSE

        mock_get.side_effect = [contracts_resp, snapshots_resp, _make_stock_resp()]

        mock_ticker = MagicMock()
        mock_yf.return_value = mock_ticker
        mock_chain = MagicMock()
        mock_chain.calls = MOCK_YF_CHAIN_CALLS
        mock_chain.puts = MOCK_YF_CHAIN_PUTS
        mock_ticker.option_chain.return_value = mock_chain

        result, err = _options_data("AAPL")
        assert err is None

        july10 = result["chain"]["2026-07-10"]
        call_180 = [c for c in july10["calls"] if c["strike"] == 180.0][0]

        # OI and volume should be populated from yfinance
        assert call_180["open_interest"] == 45000
        assert call_180["volume"] == 12500

    @patch("src.api.server.requests.get")
    @patch("yfinance.Ticker")
    def test_yfinance_failure_graceful(self, mock_yf, mock_get):
        """yfinance failure doesn't crash the whole response — OI/vol stay None."""
        contracts_resp = MagicMock()
        contracts_resp.status_code = 200
        contracts_resp.json.return_value = MOCK_CONTRACTS_RESPONSE

        snapshots_resp = MagicMock()
        snapshots_resp.status_code = 200
        snapshots_resp.json.return_value = MOCK_SNAPSHOTS_RESPONSE

        mock_get.side_effect = [contracts_resp, snapshots_resp, _make_stock_resp()]

        # yfinance raises an exception
        mock_yf.side_effect = Exception("yfinance unavailable")

        result, err = _options_data("AAPL")
        assert err is None
        assert result is not None

        # OI/volume should be None (graceful fallback)
        july10 = result["chain"]["2026-07-10"]
        for call_contract in july10["calls"]:
            assert call_contract["open_interest"] is None
            assert call_contract["volume"] is None

    @patch("src.api.server.requests.get")
    @patch("yfinance.Ticker")
    def test_no_options_for_ticker_returns_empty(self, mock_yf, mock_get):
        """Ticker with no listed options returns empty shape with 200."""
        contracts_resp = MagicMock()
        contracts_resp.status_code = 422
        contracts_resp.json.return_value = {}

        mock_get.return_value = contracts_resp

        # Set API keys so we don't short-circuit on missing keys
        result, err = _options_data("NONE")

        assert err is None
        assert result is not None
        assert result["ticker"] == "NONE"
        assert result["underlying_price"] is None
        assert result["expirations"] == []
        assert result["chain"] == {}

    @patch("src.api.server.requests.get")
    @patch("yfinance.Ticker")
    def test_empty_contracts_list_returns_empty(self, mock_yf, mock_get):
        """Alpaca returns 200 but empty contracts list."""
        contracts_resp = MagicMock()
        contracts_resp.status_code = 200
        contracts_resp.json.return_value = {"option_contracts": []}

        mock_get.return_value = contracts_resp

        result, err = _options_data("NONE")
        assert err is None
        assert result["expirations"] == []
        assert result["chain"] == {}

    @patch("src.api.server.requests.get")
    @patch("yfinance.Ticker")
    def test_missing_api_keys_returns_error(self, mock_yf, mock_get):
        """Missing Alpaca keys returns 502 error."""
        # Temporarily clear the keys
        with patch.dict(os.environ, {"ALPACA_API_KEY": "", "ALPACA_SECRET_KEY": ""}):
            # Reimport or reload would be needed — instead, patch the module-level vars
            import src.api.server as srv
            with patch.object(srv, "ALPACA_API_KEY", ""), patch.object(srv, "ALPACA_SECRET_KEY", ""):
                result, err = srv._options_data("AAPL")
                assert result is None
                assert err is not None
                assert "not configured" in err[0]["error"]
                assert err[1] == 502

    @patch("src.api.server.requests.get")
    @patch("yfinance.Ticker")
    def test_alpaca_network_error_returns_502(self, mock_yf, mock_get):
        """Connection error to Alpaca returns 502."""
        mock_get.side_effect = Exception("Connection refused")

        result, err = _options_data("AAPL")
        assert result is None
        assert err is not None
        assert err[1] == 502


# ─── Tests for summary metrics ────────────────────────────────────

class TestOptionsSummaryMetrics:
    """Verify summary metric calculations (PC ratio, max pain, ATM IV)."""

    @patch("src.api.server.requests.get")
    @patch("yfinance.Ticker")
    def test_summary_shape_and_types(self, mock_yf, mock_get):
        """Summary contains all expected fields with correct types."""
        contracts_resp = MagicMock()
        contracts_resp.status_code = 200
        contracts_resp.json.return_value = MOCK_CONTRACTS_RESPONSE

        snapshots_resp = MagicMock()
        snapshots_resp.status_code = 200
        snapshots_resp.json.return_value = MOCK_SNAPSHOTS_RESPONSE

        mock_get.side_effect = [contracts_resp, snapshots_resp, _make_stock_resp()]

        mock_ticker = MagicMock()
        mock_yf.return_value = mock_ticker
        mock_chain = MagicMock()
        mock_chain.calls = MOCK_YF_CHAIN_CALLS
        mock_chain.puts = MOCK_YF_CHAIN_PUTS
        mock_ticker.option_chain.return_value = mock_chain

        result, err = _options_data("AAPL")
        assert err is None

        summary = result["summary"]
        expected_keys = {"atm_iv", "put_call_ratio_oi", "put_call_ratio_vol",
                         "max_pain", "total_call_oi", "total_put_oi"}
        assert set(summary.keys()) == expected_keys

        # All values should be numeric or None
        for key in expected_keys:
            assert summary[key] is None or isinstance(summary[key], (int, float)), \
                f"{key} should be numeric or None, got {type(summary[key])}"

    @patch("src.api.server.requests.get")
    @patch("yfinance.Ticker")
    def test_pcr_calculation(self, mock_yf, mock_get):
        """Put/call ratios should be OI-based and volume-based counts."""
        contracts_resp = MagicMock()
        contracts_resp.status_code = 200
        contracts_resp.json.return_value = MOCK_CONTRACTS_RESPONSE

        snapshots_resp = MagicMock()
        snapshots_resp.status_code = 200
        snapshots_resp.json.return_value = MOCK_SNAPSHOTS_RESPONSE

        mock_get.side_effect = [contracts_resp, snapshots_resp, _make_stock_resp()]

        # Custom OI/volume via yfinance
        yf_calls = MagicMock()
        yf_calls.iterrows.return_value = [
            (0, {"strike": 180.0, "openInterest": 1000, "volume": 500}),
            (1, {"strike": 185.0, "openInterest": 2000, "volume": 300}),
        ]
        yf_puts = MagicMock()
        yf_puts.iterrows.return_value = [
            (0, {"strike": 180.0, "openInterest": 1500, "volume": 400}),
            (1, {"strike": 185.0, "openInterest": 2500, "volume": 200}),
        ]

        mock_ticker = MagicMock()
        mock_yf.return_value = mock_ticker
        mock_chain = MagicMock()
        mock_chain.calls = yf_calls
        mock_chain.puts = yf_puts
        mock_ticker.option_chain.return_value = mock_chain

        result, err = _options_data("AAPL")
        assert err is None

        summary = result["summary"]
        # Total call OI = 1000+2000 (2026-07-10) + 1000 (2026-07-17, only strike 180 matches) = 4000
        # Total put OI = 1500+2500 (2026-07-10) + 1500 (2026-07-17, only strike 180 matches) = 5500
        # PCR(OI) = 5500 / 4000 = 1.375
        assert summary["put_call_ratio_oi"] == 1.38  # rounded to 2 decimals
        assert summary["total_call_oi"] == 4000
        assert summary["total_put_oi"] == 5500

    @patch("src.api.server.requests.get")
    @patch("yfinance.Ticker")
    def test_pcr_with_no_call_oi_returns_none(self, mock_yf, mock_get):
        """When total_call_oi is 0, PCR should be None (avoid div-by-zero)."""
        contracts_resp = MagicMock()
        contracts_resp.status_code = 200
        contracts_resp.json.return_value = MOCK_CONTRACTS_RESPONSE

        snapshots_resp = MagicMock()
        snapshots_resp.status_code = 200
        snapshots_resp.json.return_value = {}

        mock_get.side_effect = [contracts_resp, snapshots_resp, _make_stock_resp()]

        # No OI data (all stays None, which becomes 0 in sum)
        mock_ticker = MagicMock()
        mock_yf.return_value = mock_ticker
        mock_chain = MagicMock()
        mock_chain.calls = MagicMock()
        mock_chain.calls.iterrows.return_value = []
        mock_chain.puts = MagicMock()
        mock_chain.puts.iterrows.return_value = []
        mock_ticker.option_chain.return_value = mock_chain

        result, err = _options_data("AAPL")
        assert err is None

        summary = result["summary"]
        assert summary["put_call_ratio_oi"] is None
        assert summary["put_call_ratio_vol"] is None
        assert summary["total_call_oi"] == 0
        assert summary["total_put_oi"] == 0

    @patch("src.api.server.requests.get")
    @patch("yfinance.Ticker")
    def test_max_pain_calculation(self, mock_yf, mock_get):
        """Max pain = strike with highest total loss for option buyers."""
        contracts_resp = MagicMock()
        contracts_resp.status_code = 200
        contracts_resp.json.return_value = MOCK_CONTRACTS_RESPONSE

        snapshots_resp = MagicMock()
        snapshots_resp.status_code = 200
        snapshots_resp.json.return_value = MOCK_SNAPSHOTS_RESPONSE

        mock_get.side_effect = [contracts_resp, snapshots_resp, _make_stock_resp()]

        # Underlying = 185.50
        # At strike 180: call value = (185.50 - 180) * OI, put value = 0
        # At strike 185: call value = (185.50 - 185) * OI, put value = (185 - 185.50) * OI → 0
        # With our OI: 180-strike calls OI=45000 → call pain = 5.50 * 45000 = 247500
        #               180-strike puts OI=55000 → put pain = 0
        #               185-strike calls OI=30000 → call pain = 0.50 * 30000 = 15000
        #               185-strike puts OI=60000 → put pain = 0
        # Max pain should be at 180 (highest total = 247500)
        mock_ticker = MagicMock()
        mock_yf.return_value = mock_ticker
        mock_chain = MagicMock()
        mock_chain.calls = MOCK_YF_CHAIN_CALLS
        mock_chain.puts = MOCK_YF_CHAIN_PUTS
        mock_ticker.option_chain.return_value = mock_chain

        result, err = _options_data("AAPL")
        assert err is None

        summary = result["summary"]
        assert summary["max_pain"] is not None
        # The 180 strike should have highest pain (5.50 * 45000 = 247500)
        assert summary["max_pain"] == 180.0

    @patch("src.api.server.requests.get")
    @patch("yfinance.Ticker")
    def test_atm_iv_detection(self, mock_yf, mock_get):
        """ATM IV should pick the strike closest to underlying price."""
        contracts_resp = MagicMock()
        contracts_resp.status_code = 200
        contracts_resp.json.return_value = MOCK_CONTRACTS_RESPONSE

        snapshots_resp = MagicMock()
        snapshots_resp.status_code = 200
        snapshots_resp.json.return_value = MOCK_SNAPSHOTS_RESPONSE

        mock_get.side_effect = [contracts_resp, snapshots_resp, _make_stock_resp()]

        mock_ticker = MagicMock()
        mock_yf.return_value = mock_ticker
        mock_chain = MagicMock()
        mock_chain.calls = MOCK_YF_CHAIN_CALLS
        mock_chain.puts = MOCK_YF_CHAIN_PUTS
        mock_ticker.option_chain.return_value = mock_chain

        result, err = _options_data("AAPL")
        assert err is None

        summary = result["summary"]
        # Underlying = 185.50, closest strike = 185.0
        # ATM IV = IV of 185-call or 185-put (whichever is closer — both at 0.5 diff)
        # 185-call IV = 0.28, 185-put IV = 0.30
        # 185-call first in iteration so should be 0.28
        assert summary["atm_iv"] is not None
        assert isinstance(summary["atm_iv"], float)


# ─── Tests for the Flask endpoint ─────────────────────────────────

class TestOptionsEndpoint:
    """Integration tests for GET /api/data/<ticker>/options."""

    @patch("src.api.server.requests.get")
    @patch("yfinance.Ticker")
    def test_endpoint_returns_200_with_correct_shape(self, mock_yf, mock_get, client):
        """Flask endpoint returns 200 + correct response shape."""
        contracts_resp = MagicMock()
        contracts_resp.status_code = 200
        contracts_resp.json.return_value = MOCK_CONTRACTS_RESPONSE

        snapshots_resp = MagicMock()
        snapshots_resp.status_code = 200
        snapshots_resp.json.return_value = MOCK_SNAPSHOTS_RESPONSE

        mock_get.side_effect = [contracts_resp, snapshots_resp, _make_stock_resp()]

        mock_ticker = MagicMock()
        mock_yf.return_value = mock_ticker
        mock_chain = MagicMock()
        mock_chain.calls = MOCK_YF_CHAIN_CALLS
        mock_chain.puts = MOCK_YF_CHAIN_PUTS
        mock_ticker.option_chain.return_value = mock_chain

        resp = _options_get(client, "/api/data/AAPL/options")
        assert resp.status_code == 200

        data = json.loads(resp.data)
        assert data["ticker"] == "AAPL"
        assert data["underlying_price"] == 185.50
        assert "summary" in data
        assert "atm_iv" in data["summary"]
        assert "put_call_ratio_oi" in data["summary"]
        assert "put_call_ratio_vol" in data["summary"]
        assert "max_pain" in data["summary"]
        assert "expirations" in data
        assert "chain" in data

    @patch("src.api.server.requests.get")
    def test_endpoint_no_options_returns_empty(self, mock_get, client):
        """Ticker without options returns empty chain, 200 (not error)."""
        contracts_resp = MagicMock()
        contracts_resp.status_code = 422
        mock_get.return_value = contracts_resp

        resp = _options_get(client, "/api/data/NONE/options")
        assert resp.status_code == 200

        data = json.loads(resp.data)
        assert data["chain"] == {}
        assert data["expirations"] == []

    @patch("src.api.server.requests.get")
    @patch("yfinance.Ticker")
    def test_endpoint_alpaca_failure_returns_502(self, mock_yf, mock_get, client):
        """Alpaca API failure propagates as 502."""
        mock_get.side_effect = Exception("Connection refused")

        resp = _options_get(client, "/api/data/AAPL/options")
        assert resp.status_code == 502

        data = json.loads(resp.data)
        assert "error" in data

    @patch("src.api.server.requests.get")
    @patch("yfinance.Ticker")
    def test_caching_prevents_repeated_fetches(self, mock_yf, mock_get, client):
        """Second request within 60s should use cache, not call Alpaca again."""
        contracts_resp = MagicMock()
        contracts_resp.status_code = 200
        contracts_resp.json.return_value = MOCK_CONTRACTS_RESPONSE

        snapshots_resp = MagicMock()
        snapshots_resp.status_code = 200
        snapshots_resp.json.return_value = MOCK_SNAPSHOTS_RESPONSE

        mock_get.side_effect = [contracts_resp, snapshots_resp, _make_stock_resp()]

        mock_ticker = MagicMock()
        mock_yf.return_value = mock_ticker
        mock_chain = MagicMock()
        mock_chain.calls = MOCK_YF_CHAIN_CALLS
        mock_chain.puts = MOCK_YF_CHAIN_PUTS
        mock_ticker.option_chain.return_value = mock_chain

        # First request — hits Alpaca
        resp1 = _options_get(client, "/api/data/AAPL/options")
        assert resp1.status_code == 200
        assert mock_get.call_count == 3  # contracts + snapshots + stock price

        # Reset mock call count
        mock_get.reset_mock()

        # Second request — should use cache
        resp2 = _options_get(client, "/api/data/AAPL/options")
        assert resp2.status_code == 200
        # If cached, mock_get should NOT have been called again
        assert mock_get.call_count == 0


# ─── Tests for edge cases in underlying price extraction ──────────

@patch("src.api.server.requests.get")
@patch("yfinance.Ticker")
def test_underlying_price_from_bid_ask_fallback(mock_yf, mock_get):
    """When stock price endpoint fails, use option bid/ask midpoint."""
    contracts_resp = MagicMock()
    contracts_resp.status_code = 200
    contracts_resp.json.return_value = MOCK_CONTRACTS_RESPONSE

    snapshots_no_underlying = {
        "snapshots": {
            "AAPL240712C00180000": {
                "latestTrade": {"p": 6.50, "s": 100},
                "latestQuote": {"bp": 6.40, "ap": 6.60},
            }
        }
    }
    snapshots_resp = MagicMock()
    snapshots_resp.status_code = 200
    snapshots_resp.json.return_value = snapshots_no_underlying

    mock_get.side_effect = [contracts_resp, snapshots_resp, _make_stock_resp(status_code=404)]

    mock_ticker = MagicMock()
    mock_yf.return_value = mock_ticker
    mock_chain = MagicMock()
    mock_chain.calls = MagicMock()
    mock_chain.calls.iterrows.return_value = []
    mock_chain.puts = MagicMock()
    mock_chain.puts.iterrows.return_value = []
    mock_ticker.option_chain.return_value = mock_chain

    result, err = _options_data("AAPL")
    assert err is None
    # Bid/ask midpoint = (6.40 + 6.60) / 2 = 6.50
    assert result["underlying_price"] == 6.50
