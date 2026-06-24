# Daemon Reconciliation Loop & Push Delivery Fix

## Problem

Two bugs prevent users from receiving push notifications for custom alert rules:

1. **Push delivery is dead code** — notification dicts from `_evaluate_single_rule()` never include a `rule_id` key, so `deliver_notifications()` silently skips every notification in the push channel. Additionally, `getattr(rule, "fire_push", 1)` is called on a dict — always returns the default `1`, never reading the actual DB column.

2. **Stagger gate blocks checks** — `daemon.py:check_tick()` gates every user check on `current_minute == stagger AND interval_hours_passed`. If a user's stagger minute passes without a check (daemon busy, just started), they wait up to an extra hour for the next window. A matching condition can go undetected for 2+ hours.

## Scope: 4 Files Changed

| File | Change |
|---|---|
| `src/notifications/custom_alerts.py` | Add `rule_id` to return dict |
| `src/notifications/checker.py` | Fix `getattr` → `.get()` in push gate |
| `src/notifications/daemon.py` | Add `reconciliation_tick()` alongside existing `check_tick()` |
| `src/data/ticker_fetcher.py` | **New** — rate-limited parallel yfinance fetcher |

## Change 1: Push Delivery Fix

### custom_alerts.py — `_evaluate_single_rule()` return dict

Add `rule_id` to the notification dict so `deliver_notifications()` can read it:

```python
return {
    "type": "custom_alert",
    "severity": severity,
    "title": f"⚡ {rule_name}",
    "body": body,
    "old_value": "",
    "new_value": json.dumps(value_map),
    "rule_id": rule["id"],        # ← ADDED
}
```

### checker.py — `deliver_notifications()` push gate

Fix attribute lookup on dict:

```python
# Before (dead code):
if rule and getattr(rule, "fire_push", 1):

# After:
if rule and rule.get("fire_push", 1):
```

## Change 2: Reconciliation Loop

### daemon.py — Add `reconciliation_tick()` for custom alerts

The existing `check_tick()` with its stagger schedule stays **unchanged** for full score comparisons (health, risk, Z-score). A new `reconciliation_tick()` runs alongside it in the daemon's main loop:

```python
_RECONCILIATION_INTERVAL = 60  # seconds between reconciliation ticks

def reconciliation_tick() -> None:
    """Fast reconciliation loop for custom alert rules (price, RSI, etc).

    Runs every ~60s. Fetches ticker data once per ticker (shared across
    users), evaluates all matching rules, and delivers push/Telegram
    notifications immediately when conditions are met.
    """
    rules = get_all_active_alerts_grouped_by_ticker()
    if not rules:
        return

    fetcher = TickerDataFetcher()
    for ticker, ticker_rules in rules.items():
        data = fetcher.fetch_for_alerts(ticker, ticker_rules)
        if not data:
            continue
        for rule in ticker_rules:
            result = evaluate_single_rule(rule, data, ...)
            if result:
                deliver_notifications(rule["user_id"], {ticker: [result]})
```

The daemon loop adds this call alongside the existing checks:

```python
while True:
    now = time.time()
    if now - last_reconciliation >= 60:
        reconciliation_tick()
        last_reconciliation = now
    if now - last_check_tick >= 60:
        check_tick()           # unchanged stagger logic for full scores
        last_check_tick = now
    if now - last_poll_tick >= 5:
        poll_tick()
        last_poll_tick = now
    ...
```

### Threading model

The reconciliation loop shares the daemon's main thread — it's a synchronous function called from the existing `while True` loop, same as `check_tick()` today. No new threads, no async. The parallelism for yfinance calls lives inside `TickerDataFetcher` using `concurrent.futures.ThreadPoolExecutor`.

## Change 3: TickerDataFetcher (Concurrency Layer)

New module at `src/data/ticker_fetcher.py`. One class that all daemon code paths use for getting ticker data:

```python
class TickerDataFetcher:
    """Rate-limited parallel fetcher for yfinance data.

    - Groups requests by ticker so N users watching the same ticker
      trigger one fetch instead of N fetches.
    - Caps concurrent yfinance calls to avoid rate limits.
    - Caches results per reconciliation cycle (cleared each tick).
    - Backs off tickers that return 429 / connection errors.
    """
```

### Per-cycle cache

The fetcher maintains an in-memory dict `{ticker: data}` that lives for one reconciliation tick. When 3 users all have alerts on NVDA, only one yfinance call is made. The cache is cleared at the start of each tick.

### Concurrency cap

`ThreadPoolExecutor(max_workers=5)` with a per-ticker lock so tickers queue but don't stack:

```python
def fetch_many(tickers: List[str]) -> Dict[str, Dict]:
    """Fetch N tickers in parallel, cap at 5 concurrent."""
    results = {}
    with ThreadPoolExecutor(max_workers=5) as pool:
        futures = {pool.submit(fetch_one, t): t for t in tickers}
        for future in as_completed(futures):
            ticker = futures[future]
            try:
                results[ticker] = future.result()
            except Exception:
                logger.warning(f"Failed to fetch {ticker}, skipping this cycle")
    return results
```

### Rate-limit backoff

```python
_backoff: Dict[str, float] = {}  # ticker → unix_ts when backoff expires

def fetch_one(ticker: str) -> Optional[Dict]:
    if ticker in _backoff and time.time() < _backoff[ticker]:
        return None  # skip this cycle, still in backoff

    data = _do_yfinance_call(ticker)
    if data is None and "rate limited" in last_error:
        _backoff[ticker] = time.time() + 300  # 5 min backoff
    return data
```

On 429 or network error: log warning, backoff 5 minutes, serve stale cache if available.

### Integration with existing checker

`TickerDataFetcher` replaces the ad-hoc `fetch_company_data()` calls in the reconciliation path. For the fast loop (price-only signals), it fetches just market data. The full-score-comparison path still calls `fetch_company_data()` directly (it runs on the old stagger schedule and needs fundamentals).

A helper `fetch_for_alerts()` introspects the signal types needed and fetches the minimum data:

```python
def fetch_for_alerts(ticker: str, rules: List[Dict]) -> Dict:
    needs_history = any(r["signal_id"] in HISTORY_SIGNALS for r in rules)
    needs_fundamentals = any(r["signal_id"] in FUNDAMENTAL_SIGNALS for r in rules)

    data = fetch_market_data(ticker)  # always needed (price, volume)
    if needs_history:
        data["history"] = fetch_ohlcv(ticker)
    if needs_fundamentals:
        deep_merge(data, fetch_company_data(ticker))
    return data
```

## How It All Fits Together (per-tick flow)

```
daemon.py: every 60s
  ├─ reconciliation_tick()                      ← NEW: custom alerts only
  │    ├─ Query all active custom_alert_rules
  │    ├─ Group by ticker → {NVDA: [rule1, rule2], ...}
  │    ├─ TickerDataFetcher.fetch_many([...])   ← parallel, rate-limited, cycle-cached
  │    ├─ For each ticker, for each user:
  │    │    ├─ evaluate_rule() → match?
  │    │    └─ if match → create_notification() → deliver_notifications()
  │    │         ├─ Push: rule_id is now set → send_push_notifications()
  │    │         └─ Telegram: already worked, unchanged
  │    └─ Clear cycle cache
  │
  ├─ check_tick()                               ← UNCHANGED: full score comparisons
  │    └─ stagger-gated, fetches fundamentals, delivers Telegram + in-app
  │
  └─ poll_tick()                                ← UNCHANGED: Telegram polling
       └─ polls user bots for /start, /link, /status
```

## Edge Cases

| Case | Behavior |
|---|---|
| yfinance returns garbage data | Skip ticker, log warning, next cycle retries |
| 429 rate limit | Backoff 5 min, log warning, daemon continues other tickers |
| Ticker delisted / invalid | yfinance returns None → skip, log once per hour |
| 10 users all watch NVDA | One yfinance call shared across all 10 via per-cycle cache |
| Daemon restart mid-cycle | Cycle cache lost, next tick rebuilds it. Notifications created before restart are persisted in DB |
| No active custom alerts | Reconciliation loop returns immediately, zero yfinance calls |
| New user registers + creates alert | Picked up on next reconciliation tick (within 60s) |
| Phone offline during push | Web Push protocol handles delivery — browser push service retries |

## What Doesn't Change

- The full-score-comparison `check_tick()` stays on the stagger schedule for built-in alerts (health, risk, Z-score). Those don't need sub-hour latency.
- Telegram delivery — already worked, continues working.
- Web push subscription flow — already worked, continues working.
- The systemd service file — no changes needed.
- The frontend — no changes needed.

## Verification

1. **Unit test**: `_evaluate_single_rule` return dict includes `rule_id`
2. **Unit test**: `deliver_notifications` with a notification that has `rule_id` and `fire_push=1` calls `send_push_notifications`
3. **Unit test**: `deliver_notifications` with `fire_push=0` skips push
4. **Integration**: Start daemon, create alert rule, trigger condition → verify push notification arrives (via admin test endpoint)
5. **Load test**: 20+ tickers through `TickerDataFetcher` → verify no 429s with max_workers=5
