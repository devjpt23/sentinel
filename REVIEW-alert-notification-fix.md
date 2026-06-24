# Review: Alert Notification Fix

## Reviewer Instructions

This document summarizes four bugs, one architectural change, and 61 new tests across the Sentinel alert notification system. Each change is linked to the problem it solves with the exact file and line numbers. No frontend, deployment config, or CI files were touched.

---

## Bugs Fixed

### Bug 1: Push delivery 100% dead

**Root cause:** `_evaluate_single_rule()` never set `rule_id` in its return dict. `deliver_notifications()` checks for `rule_id` to look up the rule's `fire_push` flag — with no `rule_id`, every push notification was silently skipped. Zero push notifications have ever been delivered through this code path.

**Secondary bug in same function:** `getattr(rule, "fire_push", 1)` where `rule` is a `dict` — `getattr` on a dict always raises `AttributeError`, so the fallback `1` was used. This masked the primary bug but meant per-rule fire flags were never actually read.

**Fix:**
- `src/notifications/custom_alerts.py:747` — Added `"rule_id": rule["id"]` to the return dict
- `src/notifications/checker.py:163` — Changed `getattr(rule, "fire_push", 1)` → `rule.get("fire_push", 1)`
- `src/notifications/checker.py:175` — Fixed push payload: `"rule_id": rule_id` (was `n.get("id")`, which was the notification ID, not the rule ID), added `"notification_id": n.get("id")` for correct dedup/linking

### Bug 2: Notification spam for non-cross operators

**Root cause:** Standard operators (`>`, `<`, `>=`, `<=`, `==`, `touches_upper`, `touches_lower`) fire on every check cycle while the condition holds. The 24-hour dedup uses `new_value` (a JSON blob of current values) as its dedup key — since price changes every cycle, dedup never matches. Users receive the same alert every 2 hours (or every check interval).

**Fix — hysteresis column:**
- Added `currently_triggered BOOLEAN DEFAULT 0` and `last_triggered_at TIMESTAMP` to `custom_alert_rules` via schema migration in `src/data/notification_db.py`
- `src/notifications/custom_alerts.py:598-615` — In `evaluate_custom_alerts()`, after `_evaluate_single_rule()` returns:
  - If triggered AND NOT `currently_triggered`: fire notification, set `currently_triggered = 1`
  - If triggered AND `currently_triggered`: suppress (already notified)
  - If NOT triggered AND `currently_triggered`: set `currently_triggered = 0` (condition resolved, ready to fire again)
- This is the standard threshold-alert hysteresis pattern. Works for all operator types including crosses.

### Bug 3: Custom-alert-only users invisible to daemon

**Root cause:** `check_tick()` used `get_user_ids_with_watchlist()` which queried only `user_watchlist`. Users who set up custom alerts without adding tickers to their watchlist were never checked.

**Fix:**
- `src/data/notification_db.py` — Added `get_user_ids_needing_checks()` that UNIONs `SELECT DISTINCT user_id FROM user_watchlist` with `SELECT DISTINCT user_id FROM custom_alert_rules WHERE enabled = 1`
- `src/notifications/daemon.py:54` — Changed to use `get_user_ids_needing_checks()` in `check_tick()`

### Bug 4: Stale snapshots on rule edit/disable

**Root cause:** `update_custom_alert_rule()` and `toggle_custom_alert_rule()` didn't clear `custom_alert_snapshots` or reset `currently_triggered`. A disabled rule that was re-enabled would re-fire immediately based on stale snapshots.

**Fix:**
- `src/data/notification_db.py` — In `update_custom_alert_rule()`: when `conditions` or `logic_operator` changes, reset `currently_triggered = 0` and DELETE from `custom_alert_snapshots` for that user
- `src/data/notification_db.py` — In `toggle_custom_alert_rule()`: when disabling, reset `currently_triggered = 0` and clear snapshots

### Bug 5: Infinite recursion in `get_preferences()`

**Root cause:** When `_create_default_preferences()` fails (orphan user ID with no FK target), `get_preferences()` recursively called itself, creating infinite recursion.

**Fix:**
- `src/data/notification_db.py:216-231` — Added retry-once pattern: create prefs, then check again. If the second fetch also fails, close the connection and raise `RuntimeError` with a clear message. Also fixed a pre-existing bug where `conn.close()` was called before the retry, causing a `ProgrammingError: Cannot operate on a closed database`.

---

## Architectural Change: Reconciliation Loop

### Problem

The daemon's `check_tick()` uses a stagger formula `(user_id * 37) % 60`, meaning each user is checked at most once per hour at their assigned minute. A price crossing that triggers and resolves between stagger windows is permanently missed. This is fundamentally incompatible with the "notify immediately" requirement.

### Solution

New `reconciliation_tick()` in `src/notifications/daemon.py` that runs **every 60 seconds** with no stagger, evaluating ALL active custom alert rules on ALL users.

```
daemon.py main loop (every 1s):

  every 60s:
    reconciliation_tick()   ← NEW: custom alerts, all users, no stagger
    check_tick()            ← UNCHANGED: full score comparisons (stagger-gated)

  every 5s:
    poll_tick()             ← UNCHANGED: Telegram command polling

  daily:
    maintenance_tick()      ← UNCHANGED: DB pruning
```

**Flow (lines 96-167):**
1. Query ALL active rules grouped by ticker via `get_all_active_alerts_grouped_by_ticker()`
2. Fetch price + OHLCV data for all tickers in parallel via `TickerDataFetcher` (max 5 concurrent, per-cycle cache, 5-min backoff on 429)
3. For each ticker, group rules by user_id, call `evaluate_custom_alerts()` with `history_override` to skip redundant yfinance calls
4. Deliver notifications via `deliver_notifications()` if conditions met

### Supporting: TickerDataFetcher (`src/data/ticker_fetcher.py` — new file)

- Rate-limited parallel yfinance fetcher with `ThreadPoolExecutor` (max 5 workers)
- Per-cycle cache: one yfinance call per ticker regardless of how many users watch it
- 5-minute backoff on HTTP 429 rate limit errors
- `fetch_many(tickers: Set[str])` → `Dict[str, Dict]`

### Supporting: `get_all_active_alerts_grouped_by_ticker()` (notification_db.py)

- Fetches all active rules, expands `scope='watchlist'` rules to each ticker in the user's watchlist
- Returns `{ticker: [rule_dict, ...]}` for direct iteration in the reconciliation loop

---

## Files Changed

| File | Lines | Change |
|------|-------|--------|
| `src/data/notification_db.py` | ~60 added | `get_user_ids_needing_checks()`, `get_all_active_alerts_grouped_by_ticker()`, schema migration, FK recursion fix, snapshot clearing |
| `src/data/ticker_fetcher.py` | 106 | **New file** — rate-limited parallel yfinance fetcher |
| `src/notifications/custom_alerts.py` | ~30 changed | `rule_id` in return, hysteresis logic, `history_override` param, deduped param merge |
| `src/notifications/checker.py` | ~15 changed | `getattr`→`.get()`, `fire_telegram` gate, push payload fix |
| `src/notifications/daemon.py` | ~80 changed | `reconciliation_tick()` function, main loop integration, `get_user_ids_needing_checks()` |
| `src/api/server.py` | ~25 changed | Admin reconciliation endpoint, custom-alert-only users in admin run-check |

---

## Test Coverage (61 new tests, 8 existing = 69 total)

### `tests/test_notification_db.py` (19 tests)

| Test | What it verifies |
|------|------------------|
| `TestGetUserIdsNeedingChecks` (6) | Empty DB, watchlist-only, alert-only, union dedup, disabled excluded, both sources |
| `TestGetAllActiveAlertsGroupedByTicker` (5) | Empty, single-scope grouped, watchlist-scope expanded, disabled excluded, mixed scope |
| `TestGetPreferences` (2) | Existing user (with user row), missing user raises clean RuntimeError |
| `TestSchemaMigrations` (1) | `currently_triggered` and `last_triggered_at` columns exist |
| `TestUpdateCustomAlertRule` (2) | Condition change clears triggered, name change preserves triggered |
| `TestToggleCustomAlertRule` (1) | Disable clears `currently_triggered` and sets `enabled=0` |
| `TestNotifications` (2) | Create notification, unread count per user |

### `tests/test_custom_alerts.py` (19 tests)

| Test | What it verifies |
|------|------------------|
| `TestEvaluateSingleRule` (5) | `rule_id` in return, cross w/o snapshot skips, cross w/ snapshot fires, no-match returns None, unknown signal skipped |
| `TestHysteresis` (6) | Fire once, suppress while triggered, reset on false, full fire→suppress→reset→fire cycle, cross suppressed, history_override works |
| `TestBuildMergedParams` (4) | Simple params, dict defaults, override, empty |
| `TestCrossOperators` (6) | crosses_above true/false/no-snapshot, crosses_below true/false/no-snapshot |

### `tests/test_checker.py` (6 tests)

| Test | What it verifies |
|------|------------------|
| Push delivery with rule_id | `fire_push=1` → push sent |
| Push skipped when `fire_push=0` | `fire_push=0` → push not sent |
| Telegram skipped when `fire_telegram=0` | `fire_telegram=0` → TG not sent |
| Both channels respected | Both push and TG sent when both flags set |
| Push payload keys | `rule_id`, `notification_id`, `ticker` all present |
| No rule_id | No crash, push silently skipped |

### `tests/test_ticker_fetcher.py` (8 tests)

| Test | What it verifies |
|------|------------------|
| Empty fetch | `fetch_many(set())` returns `{}` |
| Per-cycle cache | Cached ticker returned without calling yfinance |
| `clear_cycle()` | Cache cleared |
| 429 backoff | `_fetch_one` enters backoff on 429 |
| Backoff skip | Ticker in backoff skipped without yfinance call |
| Backoff expired | Expired ticker is fetched again |
| Mixed cache+fetch | Cached and uncached tickers both returned |
| `_fetch_one` success | Price and history extracted correctly |

### `tests/test_daemon.py` (5 tests)

| Test | What it verifies |
|------|------------------|
| Empty DB | No crash |
| Disabled rules only | No crash |
| No market data | Rule exists but no fetcher data → graceful handling |
| With market data | Full reconciliation flow completes |
| Multiple users, same ticker | Two rules on NVDA, one fetch, no crash |

### `tests/test_api.py` (2 added to existing 6)

| Test | What it verifies |
|------|------------------|
| Reconciliation tick returns ok | `POST /api/admin/reconciliation-tick` → 200, `ok: True` |
| Requires auth | No API key → 401 |

---

## Test Infrastructure

`tests/conftest.py` — Unified temp-file SQLite fixture that monkeypatches `_get_conn` in all three DB modules (auth_db, watchlist_db, notification_db) to connect to the same temp file, matching production's single-file setup. All 69 tests use this fixture.

`tests/helpers.py` — `seed_custom_alert_rule()`, `seed_user_watchlist()`, `make_market_data()` for test setup.
