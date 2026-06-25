# Plan: Real-Time Price Feed via Finnhub WebSocket

## Overview

Add a persistent WebSocket connection to Finnhub's free real-time API, streaming
trade prices into the daemon's alert evaluator within 2-5 seconds of a trade.
Fall back to yfinance polling when disconnected.

---

## Files Changed

| File | Action | Lines Changed |
|------|--------|--------------|
| `src/notifications/price_feed.py` | **NEW** | ~150 |
| `src/notifications/daemon.py` | EDIT | ~30 |
| `src/notifications/checker.py` | EDIT | ~15 |
| `requirements.txt` | EDIT | +1 |

Zero new infra. Zero DB changes. Zero config changes (env var only).

---

## 1. New Module: `src/notifications/price_feed.py`

### State Machine

```
STOPPED → CONNECTING → CONNECTED → SUBSCRIBED
                 ↓            ↑
            BACKOFF  ←── DISCONNECTED
```

Transitions:
- `STOPPED`: initial state, or after `stop()` called
- `CONNECTING`: `start()` called, thread spawned, connecting to WebSocket
- `CONNECTED`: WebSocket handshake complete, socket open
- `SUBSCRIBED`: subscribed to ticker symbols (can also trade from CONNECTED)
- `DISCONNECTED`: socket closed/errored. If `stop()` not called → BACKOFF → CONNECTING
- `BACKOFF`: waiting before reconnect attempt (exponential backoff)

### Signature

```python
class FinnhubPriceFeed:
    def __init__(self, api_key: str | None) -> None
    def start(self) -> None
    def stop(self) -> None
    # Called by daemon every main-loop tick:
    def drain_events(self) -> list[dict]
    # Called by daemon to refresh subscriptions (periodically):
    def refresh_subscriptions(self, tickers: set[str]) -> None
```

`drain_events()` returns a list of dicts `{"ticker": str, "price": float, "volume": int, "timestamp": int}` from the internal queue since last call. Each invocation drains the full queue and returns them as a list.

`refresh_subscriptions(tickers)` diffs against currently subscribed set. Sends `unsubscribe` for removed tickers, `subscribe` for new ones. If connection is not SUBSCRIBED, stores the desired set and applies on reconnect.

### Internal Architecture

```
Finnhub WS ──→ _on_message() ──→ queue.Queue(maxsize=1000)
                                        │
                                   drain_events()
                                        │
                                   consumed by daemon main loop
```

- WebSocket runs in a `threading.Thread` (daemon=True)
- Messages from Finnhub are enqueued into `queue.Queue`
- Daemon calls `drain_events()` each main loop tick (1s)
- Queue drops oldest item if full (warn once when first drop happens)

### Reconnection Logic

```python
_backoff = 0  # seconds
_BACKOFF_MAX = 30  # cap at 30 seconds
_BACKOFF_RESET_AFTER = 120  # reset to 0 after 120s of stable connection

# On disconnect:
if _backoff == 0:
    _backoff = 1
else:
    _backoff = min(_backoff * 2, _BACKOFF_MAX)
# Wait _backoff seconds, then reconnect

# On successful subscribe (not just connect):
# After 2 minutes of stable subscription, reset backoff
```

### Finnhub Wire Protocol

**Subscribe:**
```json
{"type": "subscribe", "symbol": "AAPL"}
```

**Unsubscribe:**
```json
{"type": "unsubscribe", "symbol": "AAPL"}
```

**Trade message received:**
```json
{
    "type": "trade",
    "data": [
        {"s": "AAPL", "p": 173.50, "v": 100000, "t": 1712345678},
        {"s": "AAPL", "p": 173.51, "v": 50000, "t": 1712345679}
    ]
}
```

Each `data` array can contain multiple trades for the same ticker (same millisecond) or
different tickers. Each entry is enqueued individually.

**Non-trade messages** (ping, status, connection info):
`type != "trade"` → silently ignored. Log at DEBUG level on first occurrence, then
stfu until feed reconnects (prevents log spam from periodic pings).

### Error Handling Matrix

| Scenario | Behavior | Log Level |
|----------|----------|-----------|
| No API key set | `start()` returns immediately, `drain_events()` always empty | WARNING (one-time) |
| DNS failure | Backoff cycle, retry | WARNING per attempt |
| Connection refused | Backoff cycle, retry | WARNING per attempt |
| TLS error | Backoff cycle, retry | WARNING per attempt |
| 403 response | Stop permanently (key invalid), set state to STOPPED | ERROR (one-time) |
| Rate limited (code 429) | Backoff 60s (not standard backoff), retry | WARNING |
| Invalid JSON on wire | Skip message, log at WARNING with msg preview (first 100 chars) | WARNING per occurrence |
| Empty ticker in subscription list | Skip, log at WARNING | WARNING (one-time per ticker) |
| Queue full | Drop oldest event | WARNING (one-time, then rate-limited to every 60s) |
| Market closed | No trades arrive. No action needed — connection stays alive, waiting | Nothing |
| Daemon kill (SIGTERM) | Thread dies, WebSocket closes | INFO |

### Backoff Reset

Once a stable subscription is held for 120 consecutive seconds without disconnect,
reset backoff to 0 (instant reconnect on next failure). This means brief blips get
binary backoff but sustained periods of stability get a fresh start.

---

## 2. Daemon Changes (`daemon.py`)

### New imports

```python
import os
from src.notifications.price_feed import FinnhubPriceFeed
```

### New variables in `main()` scope

```python
_api_key = os.environ.get("FINNHUB_API_KEY", "")
_feed = FinnhubPriceFeed(_api_key) if _api_key else None
```

### Startup (after `_startup_check()`)

```python
if _feed:
    # Load initial ticker subscriptions from active alert rules
    _refresh_price_feed_subscriptions()
    _feed.start()
    logger.info("Price feed started via Finnhub WebSocket")
else:
    logger.warning("FINNHUB_API_KEY not set — real-time price feed disabled")
```

### `_refresh_price_feed_subscriptions()` helper

```python
def _refresh_price_feed_subscriptions() -> None:
    """Query DB for tickers with active alert rules and push to price feed."""
    rules_by_ticker = get_all_active_alerts_grouped_by_ticker()
    tickers = set(rules_by_ticker.keys())
    if _feed:
        _feed.refresh_subscriptions(tickers)
```

### New main-loop tick: `price_tick()`

Called every main loop iteration (1s). Does NOT need its own timer — called directly
since events are rare and the check is cheap.

```python
def price_tick(feed: FinnhubPriceFeed | None = None, last_sub_refresh: float = 0) -> None:
    """Drain price feed events and evaluate price-based alert rules.

    Args:
        feed: The price feed instance, or None (no-op).
        last_sub_refresh: Pointer to a float in main() scope for tracking
                          when we last refreshed subscriptions.
    """
    global _fetcher
    if feed is None:
        return

    events = feed.drain_events()
    if not events:
        return

    # 1. Deduplicate: keep only the latest price per ticker per tick
    latest: dict[str, dict] = {}
    for ev in events:
        ticker = ev["ticker"].upper()
        latest[ticker] = ev  # last wins (queue is FIFO, so later = newer)

    # 2. For each ticker with a new price, evaluate alert rules
    #    Batch all tickers, then process per-user
    rules_by_ticker = get_all_active_alerts_grouped_by_ticker()

    for ticker, ev in latest.items():
        if ticker not in rules_by_ticker:
            continue

        ticker_rules = rules_by_ticker[ticker]
        price = ev["price"]

        # Build minimal data dict — just enough for _extract_price
        data = {"market": {"price": price}}

        # Group rules by user_id
        by_user: dict[int, list[dict]] = {}
        for rule in ticker_rules:
            by_user.setdefault(rule["user_id"], []).append(rule)

        for user_id, user_rules in by_user.items():
            try:
                notifications = evaluate_custom_alerts(
                    user_id, ticker, data, {},
                    history_override=pd.DataFrame(),  # empty = no OHLCV signals
                )
                if notifications:
                    # Override current_price since data dict is minimal
                    for n in notifications:
                        n["current_price"] = price
                    delivered = deliver_notifications(user_id, {ticker: notifications})
                    if delivered:
                        logger.info(
                            "Price feed: user %d, %s @ $%.2f — %d delivered",
                            user_id, ticker, price, delivered,
                        )
            except Exception:
                logger.exception("price_tick failed for user %d, %s", user_id, ticker)
```

### Subscription refresh in the main loop

Add a periodic refresh of subscriptions (every 5 minutes) to pick up new
alert rules without restarting the daemon:

```python
last_sub_refresh = 0.0
SUB_REFRESH_INTERVAL = 300  # 5 minutes
```

Inside the main loop, before other ticks:

```python
if now - last_sub_refresh >= SUB_REFRESH_INTERVAL:
    _refresh_price_feed_subscriptions()
    last_sub_refresh = now
```

### Main Loop Integration

```
while True:
    now = time.time()

    # Subscription refresh (5 min)
    if now - last_sub_refresh >= SUB_REFRESH_INTERVAL: ...

    # Price feed tick (every loop iteration — cheap if no events)
    price_tick(_feed, ...)

    # Reconciliation tick (60s)
    ...

    # Check tick (60s)
    ...

    # News check tick (15 min)
    ...

    # Telegram poll tick (5s)
    ...

    # Maintenance tick (24h)
    ...

    time.sleep(1)
```

---

## 3. Checker Changes (`checker.py`)

### Add `evaluate_price_alert()` function

```python
def evaluate_price_alert(
    user_id: int, ticker: str, price: float
) -> list[dict]:
    """Evaluate custom alert rules for a ticker using only the current price.

    Bypasses full yfinance fetch. Creates a minimal data dict with just the
    price so that _extract_price fires but OHLCV-backed extractors (RSI, MACD,
    Bollinger, SMA crossover, price change %, volume spike) return None and
    are skipped.

    Returns same format as run_check_for_ticker().
    """
    data = {"market": {"price": price}}
    # Empty scores + empty history means:
    # - price signal: works (reads data["market"]["price"])
    # - OHLCV signals: return None → skipped
    # - fundamental signals: return None → skipped
    # - news signals: return 0.0 → skipped
    notifications = evaluate_custom_alerts(
        user_id, ticker, data, {},
        history_override=pd.DataFrame(),
    )
    if notifications:
        for n in notifications:
            n["current_price"] = price
    return notifications
```

### Notes

- The existing `evaluate_custom_alerts` already handles None/NaN return values
  from extractors gracefully — it `continue`s in the condition loop (line 745).
  No changes needed there.
- The `custom_alerts.py` `_extract_price` function already works with just
  `data["market"]["price"]` (line 93). No changes needed.
- No changes to `custom_alerts.py` itself.

---

## 4. `requirements.txt` Change

```
websocket-client>=1.7.0
```

Single lightweight dependency. No heavy frameworks.

---

## 5. Env Var

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `FINNHUB_API_KEY` | No | (empty) | Finnhub API key. Not set = price feed disabled, yfinance-only. |

Get a free API key at [finnhub.io](https://finnhub.io) (no credit card,
instant key, 60 calls/min, free WebSocket).

---

## Edge Case Catalog

### Connection & Network

| # | Edge Case | Handler | Test |
|---|-----------|---------|------|
| E1 | No internet at daemon start | WebSocket `on_error` fires → backoff 1s → retry → backoff doubles → plateaus at 30s. yfinance still works during backoff. | Mock DNS failure, verify backoff chain |
| E2 | Internet drops mid-session | WebSocket `on_close` fires (no close frame) → reconnection loop. yfinance fills the gap. | Kill network after connection established, verify reconnect |
| E3 | Finnhub server down | TCP connection refused → on_error → backoff. yfinance continues. | Point WS to unreachable address |
| E4 | Finnhub returns 403 (bad key) | Log ERROR once, set state STOPPED, never retry. yfinance-only mode. | Configure invalid key, verify permanent stop |
| E5 | Finnhub rate limit (429) | Backoff 60s (override binary backoff). Then resume normal backoff. | Hard to test without hitting real rate limits — unit test the timing |
| E6 | TLS cert expired | SSL error → on_error → backoff. Same as E2. | `mock_create_connection` raises SSL error |
| E7 | Proxy / firewall blocks WS | on_error → backoff. Same as E2. | No automated test — documented in troubleshooting |

### Data Flow

| # | Edge Case | Handler | Test |
|---|-----------|---------|------|
| E8 | Finnhub sends malformed JSON | `json.loads` wrapped in try/except. Log WARNING with preview. Skip. | Inject `"not json"` into mock on_message |
| E9 | Trade data array has 0 entries | Loop over data does nothing. Not an error. | Send `{"type":"trade","data":[]}` |
| E10 | Trade data missing required fields | Check `s`, `p`, `v`, `t` keys. Skip entry if any missing, log WARNING. | Send `{"type":"trade","data":[{"s":"AAPL"}]}` |
| E11 | Trade price is 0 or negative | Enqueue but with a WARNING log. Price=0 will trigger "price > 0" conditions incorrectly — but that's a bad rule, not a data error. | Mock price=0 event |
| E12 | Trade price is NaN/null | `price is None` or `isinstance(price, str)` → skip entry, log WARNING. | Send `{"p": null}` |
| E13 | Ticker symbol has lowercase | Upper-case all tickers before enqueuing. | Send `{"s":"aapl"}` → should become "AAPL" |
| E14 | Multiple trades same ticker same second | All enqueued. `drain_events()` dedup by keeping last per ticker per call. | Send 5 AAPL trades, verify 1 output entry |
| E15 | Volume field = 0 (known Finnhub issue first hour of trading) | Enqueue normally. Volume isn't used in price signal evaluation. No impact. | Mock first-hour trade with v=0 |
| E16 | Timestamp is missing or in wrong format | Enqueue with `timestamp=0`. Price evaluation doesn't use timestamp. | Send `{"t": null}` |

### Subscription Management

| # | Edge Case | Handler | Test |
|---|-----------|---------|------|
| E17 | Ticker subscribed that has no active rules | No-op. Events are received but `rules_by_ticker` has no entry → skipped in `price_tick()`. | Subscribe "DUMMY" ticker, send trade, verify no processing |
| E18 | Ticker has rules but no "price" signal | Event still triggers `price_tick()`, which calls `evaluate_custom_alerts`. Price extractor returns value, but none of the rule's conditions use "price" signal → no match → no notification. Correct. | Create rule with "RSI > 70", verify price event doesn't fire it |
| E19 | User adds new alert rule while daemon is running | Subscription refresh every 5 minutes picks up the new ticker. If the ticker was already subscribed (other user), no new WS message needed. | Add rule for new ticker, verify it's subscribed within 5 min |
| E20 | User deletes all rules | Ticker remains subscribed but no rules match → no notifications. Subscription refresh removes ticker on next cycle. | Delete all rules, verify unsubscription within 5 min |
| E21 | Max 20-50 tickers per connection (Finnhub free tier cap) | If active tickers exceed 50, log WARNING and subscribe only first 50. The others will be evaluated on the 60s reconciliation cycle. | Create rules for 60 tickers, verify only 50 subscribed |
| E22 | Duplicate subscribe request | Finnhub ignores duplicate subscribe. No error. Safe to re-subscribe. | Send subscribe for already-subscribed ticker |
| E23 | Unsubscribe for ticker not subscribed | Finnhub ignores. Safe. | Send unsubscribe for unknown ticker |

### Threading & Queue

| # | Edge Case | Handler | Test |
|---|-----------|---------|------|
| E24 | Queue fills up (daemon can't keep up with trade volume) | Drop oldest event per ticker. Log WARNING once every 60s if queue was ever full. | Burst 2000 trades into queue with maxsize=1000 |
| E25 | Thundering herd (many price events on daemon startup after reconnect) | All enqueued. `drain_events()` dedup by ticker. If 500 AAPL trades queued, only the latest fires. | After reconnect flood, verify 1 evaluation per ticker |
| E26 | Race: daemon main loop calls `drain_events()` while WS thread is writing to queue | `queue.Queue` is thread-safe. No race. | Stress test with concurrent access |
| E27 | Thread crash (unhandled exception in WS thread) | Thread dies silently. `drain_events()` returns empty forever. Daemon needs to detect dead thread. Solution: `_thread_alive` check in `drain_events()` — if thread is dead and state != STOPPED, respawn. | Kill thread, verify respawn within 5s |
| E28 | `start()` called twice | Second call is no-op if thread is alive. Log DEBUG. | Call start() twice, verify single thread |

### Startup & Shutdown

| # | Edge Case | Handler | Test |
|---|-----------|---------|------|
| E29 | API key not set | `start()` returns immediately. `drain_events()` always returns empty list. Log WARNING once. | Run without env var, verify no crash |
| E30 | Daemon starts during market closed hours | WebSocket connects fine. Subscribe succeeds. No trades arrive. `drain_events()` returns empty. Running normally. | Start feed after-hours, verify idle |
| E31 | Daemon SIGTERM while WS is connected | `stop()` calls `ws.close()`. Thread joins with 2s timeout. If timeout exceeded, log WARNING but don't block shutdown. | Send SIGTERM, verify clean shutdown |
| E32 | `stop()` called before `start()` | No-op. Log DEBUG. | Call stop() without start() |
| E33 | Rapid start/stop cycles (daemon flapping) | Each `start()` creates fresh state. No leak. Backoff resets on each start. | Start/stop 10 times in succession |
| E34 | `refresh_subscriptions` called before `start()` | Store desired set. Apply on next `start()` → `on_open()`. | Call refresh, then start, verify subscriptions auto-apply |

### Behavioural

| # | Edge Case | Handler |
|---|-----------|---------|
| E35 | Price spike triggers alert, then immediately reverses | First trade fires the alert. Second trade is a new event — if it passes the hysteresis gate (currently_triggered), it doesn't re-fire. Correct. |
| E36 | User has "price > X" and "RSI > Y" rule (AND logic) | Price event alone won't fire this — RSI extractor returns None (no history), condition is skipped. `results` list has only the price condition's result → must be AND but only 1 result → correct behavior: price event alone doesn't fire multi-condition AND rules. |
| E37 | Price event + reconciliation tick fire simultaneously | Both call `evaluate_custom_alerts` → fine, they share no state that conflicts. The snapshot DB handles concurrency via WAL. |
| E38 | No Telegram bot configured but price alert fires | Notification created in DB. `deliver_notifications` checks telegram_enabled → 0 deliveries. Notification stays in unread queue for next UI visit. |
| E39 | User disabled notifications but has active price rule | `get_matching_custom_alert_rules` returns enabled rules. Evaluation fires, notification is created. `deliver_notifications` checks delivery prefs. Works correctly. |
| E40 | Finnhub sends trade for ticker that was just removed from watchlist | Still in subscription list until next refresh (5 min). Event arrives, evaluated, no rules match → no notification. Unsubscribed on next refresh. |

---

## Logging Strategy

| Event | Level | Example Message |
|-------|-------|-----------------|
| No API key | WARNING | "FINNHUB_API_KEY not set — real-time price feed disabled" |
| Feed started | INFO | "Finnhub price feed started (ws.finnhub.io)" |
| Feed stopped | INFO | "Finnhub price feed stopped" |
| Connected | INFO | "Finnhub WebSocket connected. Backoff reset." |
| Disconnected | WARNING | "Finnhub WebSocket disconnected: %s. Backoff: %ds" |
| Subscribed/N tickers | INFO | "Finnhub subscribed to %d tickers" |
| Unsubscribed/N tickers | DEBUG | "Finnhub unsubscribed from %d tickers" |
| Trade event | DEBUG | "Price feed: AAPL @ $173.50" |
| Alert fired | INFO | "Price feed: user 1, AAPL @ $173.50 — 2 delivered" |
| Queue full | WARNING | "Price feed queue full (1000), dropping oldest events" |
| Bad key (403) | ERROR | "Finnhub returned 403 — invalid API key. Disabling price feed." |
| Malformed message | WARNING | "Skipping malformed Finnhub message: {preview}" |
| Exceeded ticker cap | WARNING | "Active tickers (60) exceed Finnhub free cap (50). Subscribing first 50." |
| Thread died | ERROR | "Finnhub WebSocket thread died unexpectedly. Respawning." |
| Reconnect at cap | DEBUG | "Finnhub backoff at max (30s), next attempt at +30s" |

---

## Testing Strategy

### Unit Tests (`tests/test_price_feed.py`)

Focus on isolation — mock `websocket.WebSocketApp` and `queue.Queue`.

1. **test_empty_api_key**: `FinnhubPriceFeed("")` — `start()` is no-op, `drain_events()` returns `[]`
2. **test_connect_and_subscribe**: Mock successful connect. Verify subscribe messages sent for provided tickers.
3. **test_reconnect_on_disconnect**: Mock `on_close`. Verify reconnect called with backoff (1s → 2s → 4s).
4. **test_backoff_reset**: After 120s of stable connection, backoff resets to 0.
5. **test_trade_message_parsing**: Feed `on_message` a valid trade JSON. Verify `drain_events()` returns parsed event.
6. **test_malformed_json**: Feed invalid JSON. Verify no crash, WARNING logged, no events.
7. **test_missing_fields**: Feed trade with missing `p`. Verify entry skipped, WARNING logged.
8. **test_lowercase_ticker**: Feed `{"s":"aapl"}`. Verify ticker becomes "AAPL".
9. **test_queue_overflow**: Burst 2000 events into maxsize=1000 queue. Verify WARNING logged, newest events preserved.
10. **test_price_dedup**: Push 5 AAPL trades. Verify `drain_events()` returns 1 AAPL entry (the latest).
11. **test_multiple_tickers_in_one_message**: Feed `data` array with 3 tickers. Verify 3 entries in `drain_events()`.
12. **test_refresh_subscriptions**: Subscribe to {AAPL, MSFT}. Call refresh with {AAPL, GOOGL}. Verify MSFT unsubscribed, GOOGL subscribed.
13. **test_stop_while_connecting**: Call `stop()` while in BACKOFF. Verify clean exit, no reconnect.
14. **test_403_stops_permanently**: Mock 403 error. Verify state = STOPPED, `drain_events()` returns `[]`.
15. **test_feed_disabled_no_api_key**: `price_tick(None)` → no-op. Verify no errors.

### Integration Test

Manual only (needs real API key + real trades flowing):

1. Set `FINNHUB_API_KEY` in the daemon environment
2. Create a "price > current_price - 0.01" (fire on any dip) rule
3. Start daemon, observe: "Finnhub WebSocket connected" in logs
4. Wait for a trade event, observe: "Price feed: AAPL @ $173.50"
5. Verify Telegram notification arrives within 5 seconds

---

## Verification Checklist

Before marking DONE:

- [ ] `FinnhubPriceFeed` connects to `wss://ws.finnhub.io` with valid key
- [ ] Subscribes to tickers with active alert rules
- [ ] Processes trade events into `drain_events()`
- [ ] Daemon `price_tick()` evaluates price signal rules and delivers notifications
- [ ] Exponential backoff: 1s → 2s → 4s → 8s → 16s → 30s (cap)
- [ ] Backoff resets after 120s of stable connection
- [ ] 403 response permanently disables feed
- [ ] Malformed JSON doesn't crash
- [ ] Missing fields on trade entry are skipped
- [ ] Dedup: 5 trades for same ticker = 1 evaluation per `drain_events()` call
- [ ] Queue maxsize=1000, drops oldest when full
- [ ] Queue overflow warning rate-limited to once per 60s
- [ ] No API key → disabled gracefully, yfinance-only
- [ ] `websocket-client` added to `requirements.txt`
- [ ] All 15 unit tests pass
- [ ] Thread death detection respawns within 5s
- [ ] Subscription refresh every 5 minutes
- [ ] 50-ticker cap warning on free tier
- [ ] Manual integration test confirms Telegram delivery < 5s trade-to-alert
