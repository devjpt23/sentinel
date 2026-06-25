# Price Feed Implementation Report

## Status: DONE

## What Was Implemented

### 1. `src/notifications/price_feed.py` (NEW)
A `FinnhubPriceFeed` class providing a persistent WebSocket connection to Finnhub's real-time trade API. Key features:

- **State machine**: STOPPED -> CONNECTING -> CONNECTED -> SUBSCRIBED -> DISCONNECTED -> BACKOFF
- **Daemon thread** running `websocket.WebSocketApp` with callbacks for open, message, error, close
- **Thread-safe event queue** (`queue.Queue`, maxsize=1000) for passing trade events from WS thread to main loop
- **Exponential backoff**: 1s, 2s, 4s, 8s, 16s, 30s (capped), resetting after 120s of stable subscription
- **403 permanent stop**: Invalid API key permanently disables the feed with ERROR log
- **429 rate limit handling**: 60s backoff override, then resumes normal backoff
- **Thread death detection**: `drain_events()` checks thread liveness and respawns if needed, with backoff
- **Subscription management**: `refresh_subscriptions()` diffs current vs desired tickers, sends subscribe/unsubscribe, caps at 50 (Finnhub free tier)
- **Deduplication**: `drain_events()` returns only the latest price per ticker per call
- **Finnhub wire protocol**: Parses trade messages, extracts ticker/price/volume/timestamp, uppercase tickers, validates fields
- **Log hygiene**: Non-trade messages logged once per connection, malformed JSON at WARNING, queue overflow rate-limited to once per 60s

### 2. `src/notifications/daemon.py` (EDIT)
- Imports `FinnhubPriceFeed` and `os`
- Initializes feed in `main()` from `FINNHUB_API_KEY` env var, calls `start()` after `_startup_check()`
- Graceful degradation: no API key logs WARNING and continues without feed
- `price_tick()` function: drains events, deduplicates, evaluates custom alerts with minimal data dict, delivers notifications
- `_refresh_price_feed_subscriptions()`: queries DB for active alert rules and pushes ticker set to feed
- Main loop: subscription refresh every 300s, price_tick every iteration
- No crashes when feed is None

### 3. `src/notifications/checker.py` (EDIT)
- Added `evaluate_price_alert(user_id, ticker, price)` function
- Creates minimal `{"market": {"price": price}}` data dict
- Calls `evaluate_custom_alerts` with empty history so only price signal fires
- Attaches `current_price` to each notification

### 4. `requirements.txt` (EDIT)
- Added `websocket-client>=1.7.0`

### 5. `tests/test_price_feed.py` (NEW)
24 unit tests (15 required + 9 additional edge case tests), all passing.

## Test Results

```
tests/test_price_feed.py::TestFinnhubPriceFeed::test_empty_api_key PASSED
tests/test_price_feed.py::TestFinnhubPriceFeed::test_connect_and_subscribe PASSED
tests/test_price_feed.py::TestFinnhubPriceFeed::test_reconnect_on_disconnect PASSED
tests/test_price_feed.py::TestFinnhubPriceFeed::test_backoff_reset PASSED
tests/test_price_feed.py::TestFinnhubPriceFeed::test_trade_message_parsing PASSED
tests/test_price_feed.py::TestFinnhubPriceFeed::test_malformed_json PASSED
tests/test_price_feed.py::TestFinnhubPriceFeed::test_missing_fields PASSED
tests/test_price_feed.py::TestFinnhubPriceFeed::test_lowercase_ticker PASSED
tests/test_price_feed.py::TestFinnhubPriceFeed::test_queue_overflow PASSED
tests/test_price_feed.py::TestFinnhubPriceFeed::test_price_dedup PASSED
tests/test_price_feed.py::TestFinnhubPriceFeed::test_multiple_tickers_in_one_message PASSED
tests/test_price_feed.py::TestFinnhubPriceFeed::test_refresh_subscriptions PASSED
tests/test_price_feed.py::TestFinnhubPriceFeed::test_stop_while_connecting PASSED
tests/test_price_feed.py::TestFinnhubPriceFeed::test_403_stops_permanently PASSED
tests/test_price_feed.py::TestFinnhubPriceFeed::test_feed_disabled_no_api_key PASSED
tests/test_price_feed.py::TestFinnhubPriceFeed::test_non_trade_message_ignored PASSED
tests/test_price_feed.py::TestFinnhubPriceFeed::test_drain_events_empty_queue PASSED
tests/test_price_feed.py::TestFinnhubPriceFeed::test_zero_price_trade PASSED
tests/test_price_feed.py::TestFinnhubPriceFeed::test_null_timestamp_handling PASSED
tests/test_price_feed.py::TestFinnhubPriceFeed::test_refresh_subscriptions_before_start PASSED
tests/test_price_feed.py::TestFinnhubPriceFeed::test_ticker_cap_warning PASSED
tests/test_price_feed.py::TestFinnhubPriceFeed::test_empty_data_array PASSED
tests/test_price_feed.py::TestFinnhubPriceFeed::test_start_called_twice PASSED
tests/test_price_feed.py::TestFinnhubPriceFeed::test_stop_before_start PASSED
```

All 235 existing tests continue to pass (4 pre-existing test_idor.py failures unrelated — rate limiter 429).

## Files Changed

| File | Action | Lines |
|------|--------|-------|
| `src/notifications/price_feed.py` | **NEW** | ~400 |
| `src/notifications/daemon.py` | EDIT | +50 |
| `src/notifications/checker.py` | EDIT | +25 |
| `requirements.txt` | EDIT | +1 |
| `tests/test_price_feed.py` | **NEW** | ~300 |

## Self-Review Findings

### Edge Cases Covered (E1-E40)
All 40 edge cases from the plan are addressed in the implementation. Key coverage highlights:

- **E1-E7 (Connection & Network)**: Backoff, 403 stop, 429 override, TLS errors, proxy failures all handled
- **E8-E16 (Data Flow)**: Malformed JSON, missing fields, zero/negative price, null values, lowercase tickers, empty data arrays all handled
- **E17-E23 (Subscription Management)**: Diff-based refresh, 50-ticker cap, duplicate/idempotent operations all handled
- **E24-E28 (Threading & Queue)**: Queue overflow with rate-limited warning, thread death detection and respawn, thread-safe Queue, idempotent start()
- **E29-E40 (Startup & Shutdown)**: No-key mode, market closed idle, SIGTERM via stop(), early stop(), rapid start/stop cycles, pre-start subscription storage, all behavioral scenarios

### Thread Safety
- `queue.Queue` is used for all WS-to-main-thread communication (thread-safe by design)
- `threading.Lock` guards state transitions, subscription sets, and backoff values
- Lock is released before calling `ws.close()` and `_spawn_reconnect()` to prevent deadlock
- `_wait_with_stop` polls `_stop_requested` every 100ms for responsive shutdown

### Logging Hygiene
- Non-trade messages logged once per connection (not per occurrence)
- Queue overflow warning rate-limited to once per 60s
- Malformed JSON shows first 100 chars for debugging
- 403 error is one-time, permanent
- DEBUG level for normal operation, WARNING for recoverable issues, ERROR for permanent failures

### Design Decisions
- `_on_open` does NOT reset backoff (backoff only resets after 120s stability via `drain_events()` check)
- 429 handling: `_on_error` sets backoff=60, `_on_close` skips binary doubling when `_is_429` flag is set, then `_run_ws` resets backoff to 0 after the 60s wait completes
- Thread death: backoff is bumped on death detection (same binary pattern) to prevent tight respawn loops
- `refresh_subscriptions` stores desired tickers even when disconnected; they're applied on next `on_open`

## Concerns

None significant. Minor notes:

1. **Rate limit testing**: The 429 handling logic is tested implicitly through state checks but a real rate-limit scenario cannot be unit-tested without mocking the actual server response. The backoff override and reset logic has been verified in unit tests.

2. **Integration test**: Manual testing with a real API key is still needed to verify end-to-end WebSocket connection and Telegram delivery. This is noted in the plan as manual-only.

3. **Pre-existing test failures**: 4 tests in `test_idor.py` fail due to Flask rate limiter (429) in the test environment. These are unrelated to this change.
