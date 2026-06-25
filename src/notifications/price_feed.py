"""
Real-time price feed via Finnhub WebSocket.

Provides a persistent WebSocket connection to Finnhub's free real-time trade API,
streaming trade prices into the daemon's alert evaluator within 2-5 seconds of a trade.

Usage:
    feed = FinnhubPriceFeed(api_key="...")
    feed.start()
    feed.refresh_subscriptions({"AAPL", "MSFT"})
    events = feed.drain_events()
    feed.stop()
"""

import json
import logging
import queue
import threading
import time
from typing import Dict, List, Optional, Set

import websocket

logger = logging.getLogger(__name__)

_FINNHUB_WS_URL = "wss://ws.finnhub.io?token={token}"
_MAX_QUEUE_SIZE = 1000
_BACKOFF_START = 1  # seconds
_BACKOFF_MAX = 30  # seconds cap
_BACKOFF_RESET_AFTER = 120  # seconds of stability before backoff reset
_FINNHUB_FREE_TICKER_CAP = 50

# Valid state constants
_STATE_STOPPED = "STOPPED"
_STATE_CONNECTING = "CONNECTING"
_STATE_CONNECTED = "CONNECTED"
_STATE_SUBSCRIBED = "SUBSCRIBED"
_STATE_DISCONNECTED = "DISCONNECTED"
_STATE_BACKOFF = "BACKOFF"


class FinnhubPriceFeed:
    """Persistent WebSocket connection to Finnhub for real-time trade prices.

    Manages a daemon thread that connects to Finnhub's WebSocket API, subscribes
    to ticker symbols, and enqueues trade events that the daemon drains each
    main-loop tick. Handles reconnection with exponential backoff, thread death
    detection, and subscription lifecycle.
    """

    def __init__(self, api_key: Optional[str] = None) -> None:
        self._api_key = api_key
        self._state: str = _STATE_STOPPED
        self._queue: "queue.Queue[dict]" = queue.Queue(maxsize=_MAX_QUEUE_SIZE)
        self._thread: Optional[threading.Thread] = None
        self._ws: Optional[websocket.WebSocketApp] = None
        self._subscribed_tickers: Set[str] = set()
        self._desired_tickers: Set[str] = set()
        self._backoff: float = 0
        self._stable_since: Optional[float] = None
        self._lock = threading.Lock()
        self._queue_full_warned_at: float = 0.0
        self._no_key_warned: bool = False
        self._stop_requested: bool = False
        self._is_429: bool = False
        # Per-connection-id tracking for first-occurrence-only logging
        self._conn_id: int = 0
        self._non_trade_logged: Dict[int, Dict[str, bool]] = {}

    # ─── Public API ─────────────────────────────────────────────────

    def start(self) -> None:
        """Start the WebSocket connection thread.

        If no API key is set, this is a no-op (logs warning once).
        If already running, logs DEBUG and returns.
        """
        if not self._api_key:
            if not self._no_key_warned:
                logger.warning(
                    "FINNHUB_API_KEY not set — real-time price feed disabled"
                )
                self._no_key_warned = True
            return

        with self._lock:
            if self._thread and self._thread.is_alive():
                logger.debug("Finnhub price feed already running")
                return
            self._state = _STATE_CONNECTING
            self._stop_requested = False

        self._thread = threading.Thread(
            target=self._run_ws,
            daemon=True,
            name="finnhub-ws",
        )
        self._thread.start()
        logger.info("Finnhub price feed started (ws.finnhub.io)")

    def stop(self) -> None:
        """Stop the WebSocket connection and join the thread.

        Safe to call multiple times or before start(). Logs DEBUG if called
        when already stopped. Joins thread with 2s timeout and warns if the
        thread does not exit in time.
        """
        with self._lock:
            if self._state == _STATE_STOPPED:
                logger.debug("Finnhub price feed already stopped")
                return
            self._stop_requested = True
            self._state = _STATE_STOPPED

        ws = self._ws
        if ws:
            try:
                ws.close()
            except Exception:
                pass

        thread = self._thread
        if thread and thread.is_alive():
            thread.join(timeout=2.0)
            if thread.is_alive():
                logger.warning(
                    "Finnhub WebSocket thread did not stop within 2s"
                )

        with self._lock:
            self._thread = None
            self._ws = None
            self._subscribed_tickers = set()
            self._backoff = 0
            self._stable_since = None

        logger.info("Finnhub price feed stopped")

    def drain_events(self) -> List[Dict]:
        """Drain all queued price events and return them as a list.

        Deduplicates by ticker — only the latest price per ticker per call
        is returned. Also detects thread death and respawns if needed, and
        resets backoff to 0 after 120s of stable subscription.

        Returns:
            List of dicts with keys: ticker, price, volume, timestamp.
            Empty list when feed is disabled or no events queued.
        """
        if not self._api_key:
            return []

        # 1. Thread death detection and respawn
        needs_respawn = False
        with self._lock:
            if self._state != _STATE_STOPPED:
                t = self._thread
                if t and not t.is_alive():
                    needs_respawn = True
                    logger.error(
                        "Finnhub WebSocket thread died unexpectedly. Respawning."
                    )
                    self._thread = None
                    self._ws = None
                    if self._backoff == 0:
                        self._backoff = _BACKOFF_START
                    else:
                        self._backoff = min(
                            self._backoff * 2, _BACKOFF_MAX
                        )
                    self._state = _STATE_DISCONNECTED

        if needs_respawn:
            self._spawn_reconnect()

        # 2. Backoff reset check — after 120s of stable subscription,
        #    reset backoff to 0 so the next failure starts fresh.
        with self._lock:
            if (
                self._state == _STATE_SUBSCRIBED
                and self._backoff > 0
                and self._stable_since is not None
                and (time.time() - self._stable_since)
                >= _BACKOFF_RESET_AFTER
            ):
                self._backoff = 0

        # 3. Drain queue into list
        events: List[Dict] = []
        try:
            while True:
                events.append(self._queue.get_nowait())
        except queue.Empty:
            pass

        # 4. Dedup by ticker (last event per ticker wins)
        deduped: Dict[str, Dict] = {}
        for ev in events:
            ticker = ev.get("ticker", "").upper()
            if ticker:
                deduped[ticker] = ev

        return list(deduped.values())

    def refresh_subscriptions(self, tickers: Set[str]) -> None:
        """Update the set of tickers we want to subscribe to.

        Diffs against the currently subscribed set and sends subscribe/
        unsubscribe messages as needed. If the connection is not yet
        established or is in a reconnection cycle, stores the desired set
        and applies on next successful connect.

        Caps at the Finnhub free tier limit (50 tickers) and logs a
        WARNING when exceeded.

        Args:
            tickers: Set of ticker symbols to subscribe to (case-insensitive,
                     will be uppercased).
        """
        tickers = {t.upper().strip() for t in tickers if t and t.strip()}

        # Filter empty tickers
        valid: Set[str] = set()
        for t in tickers:
            ts = t.strip()
            if ts:
                valid.add(ts)
            else:
                logger.warning(
                    "Empty ticker in subscription list — skipping"
                )

        # Cap at Finnhub free tier limit
        if len(valid) > _FINNHUB_FREE_TICKER_CAP:
            logger.warning(
                "Active tickers (%d) exceed Finnhub free cap (%d). "
                "Subscribing first %d.",
                len(valid),
                _FINNHUB_FREE_TICKER_CAP,
                _FINNHUB_FREE_TICKER_CAP,
            )
            valid = set(sorted(valid)[:_FINNHUB_FREE_TICKER_CAP])

        with self._lock:
            old_desired = self._desired_tickers
            self._desired_tickers = valid

            # If connected, apply diffs via WebSocket
            if self._ws and self._state in (
                _STATE_CONNECTED,
                _STATE_SUBSCRIBED,
            ):
                to_add = valid - self._subscribed_tickers
                to_remove = self._subscribed_tickers - valid

                if to_remove:
                    self._send_unsubscribe(to_remove)
                    self._subscribed_tickers -= to_remove
                    logger.debug(
                        "Finnhub unsubscribed from %d tickers",
                        len(to_remove),
                    )

                if to_add:
                    self._send_subscribe(to_add)
                    self._subscribed_tickers |= to_add
                    logger.info(
                        "Finnhub subscribed to %d tickers",
                        len(self._subscribed_tickers),
                    )

    # ─── Internal: WebSocket Thread ─────────────────────────────────

    def _run_ws(self) -> None:
        """WebSocket connection loop with reconnection and backoff.

        Runs in a daemon thread. Creates a WebSocketApp, connects to Finnhub,
        processes messages via callbacks, and handles reconnection with
        exponential backoff when the connection drops.
        """
        while not self._stop_requested:
            # Check for stop before connecting
            with self._lock:
                if self._state == _STATE_STOPPED:
                    break

            # Backoff wait
            if self._backoff > 0:
                with self._lock:
                    self._state = _STATE_BACKOFF
                logger.info(
                    "Finnhub backoff at max (%ds), reconnecting in %ds",
                    _BACKOFF_MAX,
                    self._backoff,
                )
                if self._wait_with_stop(self._backoff):
                    return  # stop requested during backoff

            # Check for 429 reset after backoff wait completes
            with self._lock:
                if self._is_429:
                    self._is_429 = False
                    self._backoff = 0

            with self._lock:
                if self._state == _STATE_STOPPED:
                    break
                if self._state != _STATE_BACKOFF:
                    self._state = _STATE_CONNECTING

            url = _FINNHUB_WS_URL.format(token=self._api_key)
            self._conn_id += 1
            conn_id = self._conn_id

            # Reset per-connection logging for non-trade messages
            self._non_trade_logged[conn_id] = {}

            ws = websocket.WebSocketApp(
                url,
                on_open=lambda ws: self._on_open(ws, conn_id),
                on_message=lambda ws, msg: self._on_message(
                    ws, msg, conn_id
                ),
                on_error=lambda ws, err: self._on_error(
                    ws, err, conn_id
                ),
                on_close=lambda ws, close_status, close_msg: self._on_close(
                    ws, close_status, close_msg, conn_id
                ),
            )
            with self._lock:
                self._ws = ws

            # Blocking call — runs until the connection closes
            ws.run_forever()

            # Connection closed or failed — handled in _on_close
            with self._lock:
                if self._state == _STATE_STOPPED:
                    break

    def _on_open(self, ws, conn_id: int) -> None:
        """WebSocket connection established.

        Subscribes to all desired tickers, sets state to SUBSCRIBED,
        records the stability timestamp, and logs a connection message.
        """
        with self._lock:
            if self._stop_requested or self._state == _STATE_STOPPED:
                return

            # Subscribe to desired tickers
            if self._desired_tickers:
                self._send_subscribe(self._desired_tickers)
                self._subscribed_tickers = self._desired_tickers.copy()
                self._state = _STATE_SUBSCRIBED
                logger.info(
                    "Finnhub WebSocket connected. Backoff reset. "
                    "Subscribed to %d tickers.",
                    len(self._subscribed_tickers),
                )
            else:
                self._state = _STATE_CONNECTED
                logger.info(
                    "Finnhub WebSocket connected. Backoff reset. "
                    "(no tickers)"
                )

            self._stable_since = time.time()

    def _on_message(self, ws, message: str, conn_id: int) -> None:
        """Process an incoming WebSocket message from Finnhub.

        Trade messages are parsed and enqueued. Non-trade messages (ping,
        status, etc.) are logged only on their first occurrence per
        connection to avoid log spam. Malformed JSON is logged at WARNING
        and skipped.
        """
        # Parse JSON
        try:
            msg = json.loads(message)
        except json.JSONDecodeError:
            preview = (
                message[:100] if message else "(empty)"
            )
            logger.warning(
                "Skipping malformed Finnhub message: %s", preview
            )
            return

        # Only process trade messages
        msg_type = msg.get("type")
        if msg_type != "trade":
            # Log first non-trade message per connection, then stfu
            conn_logged = self._non_trade_logged.get(conn_id, {})
            msg_name = msg_type or "unknown"
            if not conn_logged.get(msg_name):
                logger.debug(
                    "Non-trade message from Finnhub: type=%s", msg_name
                )
                self._non_trade_logged[conn_id][msg_name] = True
            return

        # Process trade data
        data = msg.get("data", [])
        for entry in data:
            ticker_raw = entry.get("s", "")
            price_raw = entry.get("p")
            volume_raw = entry.get("v")
            timestamp_raw = entry.get("t")

            # Skip empty tickers
            if not ticker_raw:
                continue

            # Uppercase ticker
            ticker = ticker_raw.upper().strip()

            # Validate price
            if price_raw is None or isinstance(price_raw, str):
                logger.warning(
                    "Invalid trade price for %s: %s", ticker, price_raw
                )
                continue

            try:
                price_f = float(price_raw)
            except (ValueError, TypeError):
                logger.warning(
                    "Invalid trade price type for %s: %s",
                    ticker,
                    price_raw,
                )
                continue

            # Warn on zero/negative price but still enqueue
            if price_f <= 0:
                logger.warning(
                    "Non-positive trade price for %s: %s",
                    ticker,
                    price_f,
                )

            # Default timestamp
            if timestamp_raw is None:
                timestamp_i = 0
            else:
                try:
                    timestamp_i = int(timestamp_raw)
                except (ValueError, TypeError):
                    timestamp_i = 0

            # Default volume
            if volume_raw is None:
                volume_i = 0
            else:
                try:
                    volume_i = int(volume_raw)
                except (ValueError, TypeError):
                    volume_i = 0

            # Build event and enqueue
            event = {
                "ticker": ticker,
                "price": price_f,
                "volume": volume_i,
                "timestamp": timestamp_i,
            }

            try:
                self._queue.put_nowait(event)
            except queue.Full:
                # Drop oldest event to make room
                try:
                    self._queue.get_nowait()
                    self._queue.put_nowait(event)
                except queue.Empty:
                    pass
                now = time.time()
                if now - self._queue_full_warned_at > 60:
                    logger.warning(
                        "Price feed queue full (%d), "
                        "dropping oldest events",
                        _MAX_QUEUE_SIZE,
                    )
                    self._queue_full_warned_at = now

    def _on_error(
        self, ws, error: Exception, conn_id: int
    ) -> None:
        """Handle WebSocket error.

        On 403: permanently disables the feed (invalid API key).
        On 429: sets a 60s backoff override.
        Other errors: logged at WARNING, normal reconnection applies.
        """
        error_str = str(error)

        # Check for 403 (invalid API key) — permanent stop
        if "403" in error_str or "invalid auth" in error_str.lower():
            logger.error(
                "Finnhub returned 403 — invalid API key. "
                "Disabling price feed."
            )
            with self._lock:
                self._state = _STATE_STOPPED
                self._stop_requested = True
            return

        # Check for 429 (rate limit) — 60s backoff override
        if "429" in error_str:
            logger.warning(
                "Finnhub rate limited (429). Backing off 60s."
            )
            with self._lock:
                self._backoff = 60
                self._is_429 = True
            return

        # General error — log and let on_close handle reconnection
        logger.warning("Finnhub WebSocket error: %s", error_str)

    def _on_close(
        self,
        ws,
        close_status,
        close_msg: Optional[str],
        conn_id: int,
    ) -> None:
        """WebSocket connection closed.

        Updates state to DISCONNECTED. Applies exponential backoff
        (doubles, cap at 30s) UNLESS the connection was stable for
        120+ seconds, in which case backoff resets to 0 for a fresh
        start. Handles 429 backoff override without doubling.
        """
        with self._lock:
            if self._state == _STATE_STOPPED:
                return
            self._state = _STATE_DISCONNECTED

            # Check for 429 — backoff already set by _on_error, don't double
            if self._is_429:
                pass  # backoff stays at 60
            else:
                # Check for backoff reset (stable for 120s+ before disconnect)
                if self._stable_since is not None:
                    stable_duration = time.time() - self._stable_since
                    if stable_duration >= _BACKOFF_RESET_AFTER:
                        self._backoff = 0
                        logger.debug(
                            "Finnhub backoff reset (%ds stable)",
                            stable_duration,
                        )

                # Binary exponential backoff
                if self._backoff == 0:
                    self._backoff = _BACKOFF_START
                else:
                    self._backoff = min(
                        self._backoff * 2, _BACKOFF_MAX
                    )

            self._stable_since = None

        msg = close_msg or ""
        log_msg = (
            f"Finnhub WebSocket disconnected: {msg}. Backoff: "
            f"{self._backoff}s"
        )
        if close_msg:
            logger.warning(
                "Finnhub WebSocket disconnected: %s. Backoff: %ds",
                close_msg,
                self._backoff,
            )
        else:
            logger.warning(
                "Finnhub WebSocket disconnected. Backoff: %ds",
                self._backoff,
            )

    # ─── Internal: Helpers ─────────────────────────────────────────

    def _send_subscribe(self, tickers: Set[str]) -> None:
        """Send subscribe messages for a set of tickers via WebSocket."""
        ws = self._ws
        if not ws:
            return
        for ticker in tickers:
            try:
                ws.send(
                    json.dumps(
                        {"type": "subscribe", "symbol": ticker}
                    )
                )
            except Exception:
                logger.debug(
                    "Failed to subscribe to %s", ticker, exc_info=True
                )

    def _send_unsubscribe(self, tickers: Set[str]) -> None:
        """Send unsubscribe messages for a set of tickers via WebSocket."""
        ws = self._ws
        if not ws:
            return
        for ticker in tickers:
            try:
                ws.send(
                    json.dumps(
                        {"type": "unsubscribe", "symbol": ticker}
                    )
                )
            except Exception:
                logger.debug(
                    "Failed to unsubscribe from %s",
                    ticker,
                    exc_info=True,
                )

    def _spawn_reconnect(self) -> None:
        """Spawn a new connection thread after detecting thread death.

        Called from drain_events() when the WS thread is found dead and
        state is not STOPPED. Resets state to CONNECTING and starts a
        fresh daemon thread.
        """
        with self._lock:
            if self._state == _STATE_STOPPED:
                return
            self._state = _STATE_CONNECTING
            self._thread = threading.Thread(
                target=self._run_ws,
                daemon=True,
                name="finnhub-ws",
            )
            self._thread.start()

    def _wait_with_stop(self, seconds: float) -> bool:
        """Wait for N seconds, polling for stop every 100ms.

        Returns True if stop was requested during the wait (caller
        should exit the connection loop immediately).
        """
        interval = 0.1
        elapsed = 0.0
        while elapsed < seconds:
            if self._stop_requested:
                return True
            time.sleep(interval)
            elapsed += interval
        return False
