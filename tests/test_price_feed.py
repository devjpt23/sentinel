"""Tests for price_feed.py — FinnhubWebSocket connection, reconnection, parsing."""

import json
import time
from unittest.mock import MagicMock, call, patch

import pytest

from src.notifications.price_feed import (
    FinnhubPriceFeed,
    _BACKOFF_MAX,
    _BACKOFF_RESET_AFTER,
    _BACKOFF_START,
    _STATE_STOPPED,
    _STATE_SUBSCRIBED,
    _STATE_DISCONNECTED,
)


# ─── Fixtures ─────────────────────────────────────────────────────

@pytest.fixture
def ws_mock():
    """Patch websocket.WebSocketApp and return the class mock.

    The returned mock is the class itself (WebSocketApp); the instance
    is accessible via ``mock.return_value``.
    """
    with patch(
        "src.notifications.price_feed.websocket.WebSocketApp"
    ) as mock_cls:
        mock_inst = MagicMock()
        mock_cls.return_value = mock_inst
        yield mock_cls, mock_inst


# ─── Test Class ──────────────────────────────────────────────────

class TestFinnhubPriceFeed:
    """Unit tests for the FinnhubPriceFeed class."""

    # ── 1. Empty API Key ──────────────────────────────────────────

    def test_empty_api_key(self):
        """start() is no-op with empty key, drain_events() returns []."""
        feed = FinnhubPriceFeed("")
        feed.start()
        assert feed.drain_events() == []
        assert feed._state == _STATE_STOPPED

        # Also test with None
        feed2 = FinnhubPriceFeed(None)
        feed2.start()
        assert feed2.drain_events() == []

    # ── 2. Connect and Subscribe ──────────────────────────────────

    def test_connect_and_subscribe(self, ws_mock):
        """Should send subscribe messages for provided tickers after connect."""
        mock_cls, mock_inst = ws_mock
        feed = FinnhubPriceFeed("test_key")
        feed.refresh_subscriptions({"AAPL", "MSFT"})
        feed.start()

        # Simulate on_open callback
        on_open = mock_cls.call_args[1]["on_open"]
        on_open(mock_inst)

        # Should have sent subscribe messages
        sent_calls = mock_inst.send.call_args_list
        sent_payloads = [json.loads(c[0][0]) for c in sent_calls]
        sub_symbols = {
            p["symbol"] for p in sent_payloads
            if p["type"] == "subscribe"
        }
        assert sub_symbols == {"AAPL", "MSFT"}

    # ── 3. Reconnect on Disconnect ───────────────────────────────

    def test_reconnect_on_disconnect(self, ws_mock):
        """Backoff should double on each disconnect: 1, 2, 4, 8, 16, 30 cap."""
        mock_cls, mock_inst = ws_mock
        feed = FinnhubPriceFeed("test_key")
        feed.start()

        on_close = mock_cls.call_args[1]["on_close"]

        # First disconnect — no stable period → binary from 0
        feed._stable_since = time.time() - 5  # brief connection
        on_close(mock_inst, None, None)
        assert feed._backoff == _BACKOFF_START  # 1

        # Second disconnect
        feed._stable_since = time.time() - 10
        on_close(mock_inst, None, None)
        assert feed._backoff == 2

        # Third
        feed._stable_since = time.time() - 10
        on_close(mock_inst, None, None)
        assert feed._backoff == 4

        # Fourth
        feed._stable_since = time.time() - 10
        on_close(mock_inst, None, None)
        assert feed._backoff == 8

        # Fifth
        feed._stable_since = time.time() - 10
        on_close(mock_inst, None, None)
        assert feed._backoff == 16

        # Sixth — cap at 30
        feed._stable_since = time.time() - 10
        on_close(mock_inst, None, None)
        assert feed._backoff == _BACKOFF_MAX  # 30

        # Seventh — stays at 30
        feed._stable_since = time.time() - 10
        on_close(mock_inst, None, None)
        assert feed._backoff == _BACKOFF_MAX

    # ── 4. Backoff Reset after 120s stability ────────────────────

    def test_backoff_reset(self, ws_mock):
        """Backoff resets to 0 after 120s of stable subscription."""
        mock_cls, mock_inst = ws_mock
        feed = FinnhubPriceFeed("test_key")
        feed.start()

        # Accumulate some backoff
        on_close = mock_cls.call_args[1]["on_close"]
        feed._stable_since = time.time() - 5
        on_close(mock_inst, None, None)
        assert feed._backoff == _BACKOFF_START

        # Simulate reconnection and longer stability
        feed._state = _STATE_SUBSCRIBED
        feed._stable_since = time.time() - _BACKOFF_RESET_AFTER - 10
        feed._backoff = 8

        # drain_events should detect stability and reset
        feed.drain_events()
        assert feed._backoff == 0

    # ── 5. Trade Message Parsing ─────────────────────────────────

    def test_trade_message_parsing(self, ws_mock):
        """Valid trade JSON produces parsed events via drain_events()."""
        mock_cls, mock_inst = ws_mock
        feed = FinnhubPriceFeed("test_key")
        feed.start()

        on_message = mock_cls.call_args[1]["on_message"]
        on_message(
            mock_inst,
            json.dumps({
                "type": "trade",
                "data": [{
                    "s": "AAPL",
                    "p": 173.50,
                    "v": 100000,
                    "t": 1712345678,
                }],
            }),
        )

        events = feed.drain_events()
        assert len(events) == 1
        assert events[0]["ticker"] == "AAPL"
        assert events[0]["price"] == 173.50
        assert events[0]["volume"] == 100000
        assert events[0]["timestamp"] == 1712345678

    # ── 6. Malformed JSON ────────────────────────────────────────

    def test_malformed_json(self, ws_mock):
        """Invalid JSON does not crash and produces no events."""
        mock_cls, mock_inst = ws_mock
        feed = FinnhubPriceFeed("test_key")
        feed.start()

        on_message = mock_cls.call_args[1]["on_message"]
        on_message(mock_inst, "not valid json")

        assert feed.drain_events() == []

    # ── 7. Missing Fields on Trade Entry ─────────────────────────

    def test_missing_fields(self, ws_mock):
        """Trade with missing price field is skipped."""
        mock_cls, mock_inst = ws_mock
        feed = FinnhubPriceFeed("test_key")
        feed.start()

        on_message = mock_cls.call_args[1]["on_message"]
        on_message(
            mock_inst,
            json.dumps({
                "type": "trade",
                "data": [{"s": "AAPL"}],  # no p, v, t
            }),
        )

        events = feed.drain_events()
        assert len(events) == 0

    # ── 8. Lowercase Ticker ──────────────────────────────────────

    def test_lowercase_ticker(self, ws_mock):
        """Lowercase ticker symbol is uppercased."""
        mock_cls, mock_inst = ws_mock
        feed = FinnhubPriceFeed("test_key")
        feed.start()

        on_message = mock_cls.call_args[1]["on_message"]
        on_message(
            mock_inst,
            json.dumps({
                "type": "trade",
                "data": [{
                    "s": "aapl",
                    "p": 173.50,
                    "v": 1000,
                    "t": 12345,
                }],
            }),
        )

        events = feed.drain_events()
        assert len(events) == 1
        assert events[0]["ticker"] == "AAPL"

    # ── 9. Queue Overflow ────────────────────────────────────────

    def test_queue_overflow(self, ws_mock):
        """2000 events into maxsize=1000 queue preserves newest events."""
        mock_cls, mock_inst = ws_mock
        feed = FinnhubPriceFeed("test_key")
        feed.start()

        on_message = mock_cls.call_args[1]["on_message"]
        # Burst 2000 events for the same ticker
        for i in range(2000):
            on_message(
                mock_inst,
                json.dumps({
                    "type": "trade",
                    "data": [{
                        "s": "AAPL",
                        "p": float(100 + i / 100),
                        "v": 1000,
                        "t": 1000 + i,
                    }],
                }),
            )

        events = feed.drain_events()
        # After dedup, only 1 AAPL event
        assert len(events) == 1
        # Price should be the latest (~119.99)
        assert events[0]["price"] == pytest.approx(119.99, rel=0.01)

    # ── 10. Price Dedup per drain_events() Call ─────────────────

    def test_price_dedup(self, ws_mock):
        """5 AAPL trades → 1 event per drain_events() (the latest)."""
        mock_cls, mock_inst = ws_mock
        feed = FinnhubPriceFeed("test_key")
        feed.start()

        on_message = mock_cls.call_args[1]["on_message"]
        for i in range(5):
            on_message(
                mock_inst,
                json.dumps({
                    "type": "trade",
                    "data": [{
                        "s": "AAPL",
                        "p": float(170 + i),
                        "v": 1000,
                        "t": 12345 + i,
                    }],
                }),
            )

        events = feed.drain_events()
        assert len(events) == 1
        assert events[0]["price"] == 174.0  # the latest

    # ── 11. Multiple Tickers in One Message ─────────────────────

    def test_multiple_tickers_in_one_message(self, ws_mock):
        """Trade data array with 3 tickers produces 3 events."""
        mock_cls, mock_inst = ws_mock
        feed = FinnhubPriceFeed("test_key")
        feed.start()

        on_message = mock_cls.call_args[1]["on_message"]
        on_message(
            mock_inst,
            json.dumps({
                "type": "trade",
                "data": [
                    {"s": "AAPL", "p": 150.0, "v": 1000, "t": 1},
                    {"s": "MSFT", "p": 300.0, "v": 2000, "t": 2},
                    {"s": "GOOGL", "p": 140.0, "v": 3000, "t": 3},
                ],
            }),
        )

        events = feed.drain_events()
        assert len(events) == 3
        tickers = {e["ticker"] for e in events}
        assert tickers == {"AAPL", "MSFT", "GOOGL"}

    # ── 12. Refresh Subscriptions ───────────────────────────────

    def test_refresh_subscriptions(self, ws_mock):
        """Unsubscribes removed tickers and subscribes new ones."""
        mock_cls, mock_inst = ws_mock
        feed = FinnhubPriceFeed("test_key")
        feed.start()

        # Connect first
        on_open = mock_cls.call_args[1]["on_open"]
        on_open(mock_inst)

        # Initially subscribe to AAPL, MSFT
        mock_inst.send.reset_mock()
        feed.refresh_subscriptions({"AAPL", "MSFT"})

        # Now change subscription set — remove MSFT, add GOOGL
        mock_inst.send.reset_mock()
        feed.refresh_subscriptions({"AAPL", "GOOGL"})

        # Check that unsubscribe was sent for MSFT and subscribe for GOOGL
        sent_calls = mock_inst.send.call_args_list
        sent_payloads = [json.loads(c[0][0]) for c in sent_calls]
        unsub_symbols = {
            p["symbol"] for p in sent_payloads
            if p["type"] == "unsubscribe"
        }
        sub_symbols = {
            p["symbol"] for p in sent_payloads
            if p["type"] == "subscribe"
        }
        assert "MSFT" in unsub_symbols
        assert "GOOGL" in sub_symbols
        assert "AAPL" not in unsub_symbols  # still in both sets

    # ── 13. Stop While Connecting ────────────────────────────────

    def test_stop_while_connecting(self, ws_mock):
        """stop() called while thread is alive cleans up cleanly."""
        mock_cls, mock_inst = ws_mock
        feed = FinnhubPriceFeed("test_key")
        feed.start()

        # Call stop immediately while thread might be starting
        feed.stop()
        assert feed._state == _STATE_STOPPED
        assert feed._thread is None or not feed._thread.is_alive()

    # ── 14. 403 Stops Permanently ───────────────────────────────

    def test_403_stops_permanently(self, ws_mock):
        """403 error permanently disables the feed."""
        mock_cls, mock_inst = ws_mock
        feed = FinnhubPriceFeed("test_key")
        feed.start()

        on_error = mock_cls.call_args[1]["on_error"]
        on_error(mock_inst, Exception("403 Forbidden"))

        assert feed._state == _STATE_STOPPED
        assert feed.drain_events() == []

    # ── 15. Feed Disabled (No API Key) ──────────────────────────

    def test_feed_disabled_no_api_key(self):
        """Calling drain_events with empty key is safe (no crash)."""
        feed = FinnhubPriceFeed("")
        # Should not crash, should not connect
        feed.start()
        result = feed.drain_events()
        assert result == []

    # ── Additional edge case tests ──────────────────────────────

    def test_non_trade_message_ignored(self, ws_mock):
        """Non-trade messages are silently ignored (no events produced)."""
        mock_cls, mock_inst = ws_mock
        feed = FinnhubPriceFeed("test_key")
        feed.start()

        on_message = mock_cls.call_args[1]["on_message"]
        # Simulate a ping message
        on_message(mock_inst, json.dumps({"type": "ping"}))
        # Simulate a status message
        on_message(
            mock_inst,
            json.dumps({"type": "connection", "status": "ok"}),
        )

        events = feed.drain_events()
        assert len(events) == 0

    def test_drain_events_empty_queue(self, ws_mock):
        """drain_events returns empty list when queue is empty."""
        mock_cls, mock_inst = ws_mock
        feed = FinnhubPriceFeed("test_key")
        feed.start()

        events = feed.drain_events()
        assert events == []

    def test_zero_price_trade(self, ws_mock):
        """Trade with price=0 is enqueued (with warning), not skipped."""
        mock_cls, mock_inst = ws_mock
        feed = FinnhubPriceFeed("test_key")
        feed.start()

        on_message = mock_cls.call_args[1]["on_message"]
        on_message(
            mock_inst,
            json.dumps({
                "type": "trade",
                "data": [{"s": "AAPL", "p": 0.0, "v": 1000, "t": 123}],
            }),
        )

        events = feed.drain_events()
        assert len(events) == 1
        assert events[0]["price"] == 0.0

    def test_null_timestamp_handling(self, ws_mock):
        """Missing timestamp defaults to 0."""
        mock_cls, mock_inst = ws_mock
        feed = FinnhubPriceFeed("test_key")
        feed.start()

        on_message = mock_cls.call_args[1]["on_message"]
        on_message(
            mock_inst,
            json.dumps({
                "type": "trade",
                "data": [{"s": "AAPL", "p": 150.0, "v": 1000}],  # no t
            }),
        )

        events = feed.drain_events()
        assert len(events) == 1
        assert events[0]["timestamp"] == 0

    def test_refresh_subscriptions_before_start(self, ws_mock):
        """Calling refresh_subscriptions before start stores tickers."""
        feed = FinnhubPriceFeed("test_key")
        feed.refresh_subscriptions({"AAPL"})
        assert feed._desired_tickers == {"AAPL"}

        # After start, on_open should subscribe to AAPL
        mock_cls, mock_inst = ws_mock
        with patch(
            "src.notifications.price_feed.websocket.WebSocketApp"
        ) as mock_cls2:
            mock_inst2 = MagicMock()
            mock_cls2.return_value = mock_inst2
            feed.start()
            on_open = mock_cls2.call_args[1]["on_open"]
            on_open(mock_inst2)

            sent_calls = mock_inst2.send.call_args_list
            sent_payloads = [
                json.loads(c[0][0]) for c in sent_calls
            ]
            sub_symbols = {
                p["symbol"] for p in sent_payloads
                if p["type"] == "subscribe"
            }
            assert "AAPL" in sub_symbols

    def test_ticker_cap_warning(self, ws_mock):
        """More than 50 tickers logs a warning and caps at 50."""
        feed = FinnhubPriceFeed("test_key")
        many_tickers = {f"T{i:04d}" for i in range(60)}
        feed.refresh_subscriptions(many_tickers)
        assert len(feed._desired_tickers) <= 50

    def test_empty_data_array(self, ws_mock):
        """Trade message with empty data array produces no events."""
        mock_cls, mock_inst = ws_mock
        feed = FinnhubPriceFeed("test_key")
        feed.start()

        on_message = mock_cls.call_args[1]["on_message"]
        on_message(
            mock_inst,
            json.dumps({"type": "trade", "data": []}),
        )

        events = feed.drain_events()
        assert len(events) == 0

    def test_start_called_twice(self, ws_mock):
        """Calling start() twice should not create a second thread."""
        mock_cls, mock_inst = ws_mock
        feed = FinnhubPriceFeed("test_key")
        feed.start()
        thread1 = feed._thread

        feed.start()  # second call — should be no-op
        thread2 = feed._thread

        assert thread1 is thread2

    def test_stop_before_start(self):
        """Calling stop() before start() is a safe no-op."""
        feed = FinnhubPriceFeed("test_key")
        feed.stop()  # should not crash
        assert feed._state == _STATE_STOPPED
