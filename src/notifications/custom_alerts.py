"""
Custom Alert evaluation engine.

Provides a catalog of signals (price, technical, fundamental) and an evaluator
that checks user-defined alert rules against live data. Designed to plug into
the existing checker.py pipeline with minimal changes.

Usage:
    from src.notifications.custom_alerts import evaluate_custom_alerts

    notifications = evaluate_custom_alerts(user_id, ticker, data, scores)
"""

import json
import logging
from typing import Optional, List, Dict

import pandas as pd
import yfinance as yf

from src.data.notification_db import (
    get_matching_custom_alert_rules,
    get_custom_alert_snapshot,
    save_custom_alert_snapshot,
    update_custom_alert_rule,
)

logger = logging.getLogger(__name__)

# ─── Per-cycle history cache ──────────────────────────────────
# Cleared at the start of each evaluate_custom_alerts() call so that
# technical indicators share one OHLCV fetch per ticker per check cycle.
_history_cache: Dict[str, pd.DataFrame] = {}


def _get_history(ticker: str) -> pd.DataFrame:
    """Fetch 6-month OHLCV history with per-cycle in-memory caching."""
    if ticker not in _history_cache:
        try:
            t = yf.Ticker(ticker)
            df = t.history(period="6mo")
            if df is not None and not df.empty:
                _history_cache[ticker] = df
            else:
                _history_cache[ticker] = pd.DataFrame()
        except Exception:
            _history_cache[ticker] = pd.DataFrame()
    return _history_cache.get(ticker, pd.DataFrame())


# ─── Operator Functions ───────────────────────────────────────

def _op_gt(current: float, threshold: float) -> bool:
    return current > threshold


def _op_lt(current: float, threshold: float) -> bool:
    return current < threshold


def _op_gte(current: float, threshold: float) -> bool:
    return current >= threshold


def _op_lte(current: float, threshold: float) -> bool:
    return current <= threshold


def _op_eq(current: float, threshold: float) -> bool:
    return abs(current - threshold) < 0.001


def _op_crosses_above(current: float, previous: Optional[float], threshold: float) -> bool:
    """True when previous <= threshold AND current > threshold."""
    if previous is None:
        return False
    return previous <= threshold and current > threshold


def _op_crosses_below(current: float, previous: Optional[float], threshold: float) -> bool:
    """True when previous >= threshold AND current < threshold."""
    if previous is None:
        return False
    return previous >= threshold and current < threshold


# ─── Signal Extractors ────────────────────────────────────────
# Each takes (data, scores, history, params) and returns Optional[float].
# Return None when the underlying data is missing (rule silently skipped).

def _extract_price(data: Dict, scores: Dict, history: pd.DataFrame, params: Dict) -> Optional[float]:
    market = data.get("market", {})
    return market.get("price")


def _extract_price_change_abs(data: Dict, scores: Dict, history: pd.DataFrame, params: Dict) -> Optional[float]:
    """Absolute dollar change over N days (e.g., +$1.50 or -$0.80)."""
    days = int(params.get("days", 1))
    if history is None or history.empty or "Close" not in history.columns:
        return None
    closes = history["Close"]
    if len(closes) < days + 1:
        return None
    old_price = float(closes.iloc[-(days + 1)])
    new_price = float(closes.iloc[-1])
    return new_price - old_price


def _extract_price_change_pct(data: Dict, scores: Dict, history: pd.DataFrame, params: Dict) -> Optional[float]:
    days = int(params.get("days", 5))
    if history is None or history.empty or "Close" not in history.columns:
        return None
    closes = history["Close"]
    if len(closes) < days + 1:
        return None
    old_price = float(closes.iloc[-(days + 1)])
    new_price = float(closes.iloc[-1])
    if old_price == 0:
        return None
    return ((new_price - old_price) / old_price) * 100.0


def _extract_distance_52w_high(data: Dict, scores: Dict, history: pd.DataFrame, params: Dict) -> Optional[float]:
    market = data.get("market", {})
    high = market.get("52w_high")
    price = market.get("price")
    if high is None or price is None or high == 0:
        return None
    return ((high - price) / high) * 100.0


def _extract_distance_52w_low(data: Dict, scores: Dict, history: pd.DataFrame, params: Dict) -> Optional[float]:
    market = data.get("market", {})
    low = market.get("52w_low")
    price = market.get("price")
    if low is None or price is None or low == 0:
        return None
    return ((price - low) / low) * 100.0


def _extract_volume_spike(data: Dict, scores: Dict, history: pd.DataFrame, params: Dict) -> Optional[float]:
    if history is None or history.empty or "Volume" not in history.columns:
        return None
    avg_vol = data.get("market", {}).get("avg_volume")
    if avg_vol is None or avg_vol == 0:
        return None
    current_vol = float(history["Volume"].iloc[-1])
    return current_vol / avg_vol


def _extract_sma_crossover(data: Dict, scores: Dict, history: pd.DataFrame, params: Dict) -> Optional[float]:
    """Returns 1.0 if price > SMA, 0.0 otherwise (for crosses detection)."""
    period = int(params.get("period", 50))
    if history is None or history.empty or "Close" not in history.columns:
        return None
    closes = history["Close"]
    if len(closes) < period:
        return None
    sma = float(closes.rolling(window=period).mean().iloc[-1])
    price = float(closes.iloc[-1])
    if pd.isna(sma):
        return None
    return 1.0 if price > sma else 0.0


def _extract_rsi(data: Dict, scores: Dict, history: pd.DataFrame, params: Dict) -> Optional[float]:
    """Compute RSI(14) from price history. Returns 0-100 value."""
    period = 14
    if history is None or history.empty or "Close" not in history.columns:
        return None
    closes = history["Close"]
    if len(closes) < period + 1:
        return None

    deltas = closes.diff()
    gains = deltas.clip(lower=0)
    losses = (-deltas).clip(lower=0)

    # Wilder's smoothing
    avg_gain = float(gains.iloc[1:period + 1].mean())
    avg_loss = float(losses.iloc[1:period + 1].mean())

    for i in range(period + 1, len(closes)):
        avg_gain = (avg_gain * (period - 1) + float(gains.iloc[i])) / period
        avg_loss = (avg_loss * (period - 1) + float(losses.iloc[i])) / period

    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return 100.0 - (100.0 / (1.0 + rs))


def _extract_macd_crossover(data: Dict, scores: Dict, history: pd.DataFrame, params: Dict) -> Optional[float]:
    """Returns 1.0 if MACD > signal line, 0.0 otherwise (for crosses detection)."""
    if history is None or history.empty or "Close" not in history.columns:
        return None
    closes = history["Close"]
    if len(closes) < 34:  # need at least 26 + 9 periods
        return None

    ema12 = closes.ewm(span=12, adjust=False).mean()
    ema26 = closes.ewm(span=26, adjust=False).mean()
    macd_line = ema12 - ema26
    signal_line = macd_line.ewm(span=9, adjust=False).mean()

    macd_val = float(macd_line.iloc[-1])
    signal_val = float(signal_line.iloc[-1])

    if pd.isna(macd_val) or pd.isna(signal_val):
        return None
    return 1.0 if macd_val > signal_val else 0.0


def _extract_bollinger(data: Dict, scores: Dict, history: pd.DataFrame, params: Dict) -> Optional[float]:
    """Returns Bollinger %B: 0=lower band, 1=upper band, can exceed [0,1].

    touches_upper operator fires when %B >= 1.0; touches_lower when %B <= 0.0.
    """
    period = 20
    if history is None or history.empty or "Close" not in history.columns:
        return None
    closes = history["Close"]
    if len(closes) < period:
        return None

    sma = closes.rolling(window=period).mean()
    std = closes.rolling(window=period).std()

    price = float(closes.iloc[-1])
    middle = float(sma.iloc[-1])
    std_val = float(std.iloc[-1])

    if pd.isna(middle) or pd.isna(std_val) or std_val == 0:
        return None

    upper = middle + 2 * std_val
    lower = middle - 2 * std_val

    # %B = (price - lower) / (upper - lower)
    return (price - lower) / (upper - lower) if (upper - lower) != 0 else 0.5


# ─── Score-backed extractors ──────────────────────────────────

def _extract_score(data: Dict, scores: Dict, history: pd.DataFrame, params: Dict) -> Optional[float]:
    """Generic extractor for any score key in the scores dict."""
    score_key = params.get("score_key")
    if score_key is None:
        return None
    val = scores.get(score_key)
    if val is None:
        return None
    return float(val)


def _extract_valuation(data: Dict, scores: Dict, history: pd.DataFrame, params: Dict) -> Optional[float]:
    """Generic extractor for valuation dict fields."""
    data_key = params.get("data_key")
    if data_key is None:
        return None
    val = data.get("valuation", {}).get(data_key)
    if val is None:
        return None
    return float(val)


def _extract_health(data: Dict, scores: Dict, history: pd.DataFrame, params: Dict) -> Optional[float]:
    """Generic extractor for health dict fields."""
    data_key = params.get("data_key")
    if data_key is None:
        return None
    val = data.get("health", {}).get(data_key)
    if val is None:
        return None
    return float(val)


def _extract_per_share(data: Dict, scores: Dict, history: pd.DataFrame, params: Dict) -> Optional[float]:
    """Generic extractor for per_share dict fields."""
    data_key = params.get("data_key")
    if data_key is None:
        return None
    val = data.get("per_share", {}).get(data_key)
    if val is None:
        return None
    return float(val)


# ─── Signal Catalog ───────────────────────────────────────────

SIGNAL_CATALOG: Dict[str, Dict] = {
    # ── Price & Volume ──────────────────────────────
    "price": {
        "category": "Price & Volume",
        "name": "Current Price",
        "unit": "USD",
        "description": "The latest trading price",
        "operators": [">", "<", ">=", "<=", "==", "crosses_above", "crosses_below"],
        "requires_history": False,
        "extractor": _extract_price,
        "params": {},
    },
    "price_change_abs": {
        "category": "Price & Volume",
        "name": "Price Change ($)",
        "unit": "USD",
        "description": "Absolute dollar change over N trading days (+ means up, - means down)",
        "operators": [">", "<", ">=", "<=", "crosses_above", "crosses_below"],
        "requires_history": True,
        "extractor": _extract_price_change_abs,
        "params": {"days": {"type": "int", "default": 1, "min": 1, "max": 90}},
    },
    "price_change_pct": {
        "category": "Price & Volume",
        "name": "Price Change %",
        "unit": "%",
        "description": "Percent change over N trading days",
        "operators": [">", "<", ">=", "<="],
        "requires_history": True,
        "extractor": _extract_price_change_pct,
        "params": {"days": {"type": "int", "default": 5, "min": 1, "max": 365}},
    },
    "distance_52w_high": {
        "category": "Price & Volume",
        "name": "% Below 52-Week High",
        "unit": "%",
        "description": "How far below the 52-week high (0% = at high)",
        "operators": [">", "<", ">=", "<="],
        "requires_history": False,
        "extractor": _extract_distance_52w_high,
        "params": {},
    },
    "distance_52w_low": {
        "category": "Price & Volume",
        "name": "% Above 52-Week Low",
        "unit": "%",
        "description": "How far above the 52-week low (0% = at low)",
        "operators": [">", "<", ">=", "<="],
        "requires_history": False,
        "extractor": _extract_distance_52w_low,
        "params": {},
    },
    "volume_spike": {
        "category": "Price & Volume",
        "name": "Volume vs Average",
        "unit": "×",
        "description": "Current daily volume divided by average volume",
        "operators": [">", "<", ">=", "<="],
        "requires_history": True,
        "extractor": _extract_volume_spike,
        "params": {},
    },
    "sma_crossover": {
        "category": "Price & Volume",
        "name": "Price vs SMA",
        "unit": "",
        "description": "Price relative to Simple Moving Average",
        "operators": ["crosses_above", "crosses_below"],
        "requires_history": True,
        "extractor": _extract_sma_crossover,
        "params": {"period": {"type": "choice", "default": 50, "options": [20, 50, 200]}},
    },
    # ── Technical ───────────────────────────────────
    "rsi": {
        "category": "Technical",
        "name": "RSI (14)",
        "unit": "",
        "description": "Relative Strength Index, 0-100. Above 70 = overbought, below 30 = oversold",
        "operators": [">", "<", ">=", "<=", "crosses_above", "crosses_below"],
        "requires_history": True,
        "extractor": _extract_rsi,
        "params": {},
    },
    "macd": {
        "category": "Technical",
        "name": "MACD Signal Cross",
        "unit": "",
        "description": "MACD line crossing the signal line (bullish/bearish)",
        "operators": ["crosses_above", "crosses_below"],
        "requires_history": True,
        "extractor": _extract_macd_crossover,
        "params": {},
    },
    "bollinger": {
        "category": "Technical",
        "name": "Bollinger Band Touch",
        "unit": "",
        "description": "Price touching upper or lower Bollinger Band (20,2)",
        "operators": ["touches_upper", "touches_lower"],
        "requires_history": True,
        "extractor": _extract_bollinger,
        "params": {},
    },
    # ── Fundamental ─────────────────────────────────
    "health_score": {
        "category": "Fundamental",
        "name": "Health Score",
        "unit": "pts",
        "description": "Composite financial health score (0-100)",
        "operators": [">", "<", ">=", "<=", "crosses_above", "crosses_below"],
        "requires_history": False,
        "extractor": _extract_score,
        "params": {"score_key": "health_score"},
    },
    "fscore": {
        "category": "Fundamental",
        "name": "F-Score",
        "unit": "pts",
        "description": "Piotroski F-Score (0-9)",
        "operators": [">", "<", ">=", "<="],
        "requires_history": False,
        "extractor": _extract_score,
        "params": {"score_key": "fscore"},
    },
    "risk_score": {
        "category": "Fundamental",
        "name": "Risk Score",
        "unit": "pts",
        "description": "Risk assessment score (0-100, higher = safer)",
        "operators": [">", "<", ">=", "<="],
        "requires_history": False,
        "extractor": _extract_score,
        "params": {"score_key": "risk_score"},
    },
    "zscore": {
        "category": "Fundamental",
        "name": "Altman Z-Score",
        "unit": "",
        "description": "Bankruptcy risk score. >2.6 Safe, 1.1-2.6 Grey, <1.1 Distress",
        "operators": [">", "<", ">=", "<="],
        "requires_history": False,
        "extractor": _extract_score,
        "params": {"score_key": "zscore"},
    },
    "pe_ttm": {
        "category": "Fundamental",
        "name": "P/E Ratio (TTM)",
        "unit": "×",
        "description": "Price to trailing twelve months earnings",
        "operators": [">", "<", ">=", "<="],
        "requires_history": False,
        "extractor": _extract_valuation,
        "params": {"data_key": "pe_ttm"},
    },
    "pb_ratio": {
        "category": "Fundamental",
        "name": "P/B Ratio",
        "unit": "×",
        "description": "Price to book value",
        "operators": [">", "<", ">=", "<="],
        "requires_history": False,
        "extractor": _extract_valuation,
        "params": {"data_key": "pb_ratio"},
    },
    "debt_to_equity": {
        "category": "Fundamental",
        "name": "Debt/Equity Ratio",
        "unit": "%",
        "description": "Total debt divided by equity (as %)",
        "operators": [">", "<", ">=", "<="],
        "requires_history": False,
        "extractor": _extract_health,
        "params": {"data_key": "debt_to_equity"},
    },
    "dividend_yield": {
        "category": "Fundamental",
        "name": "Dividend Yield",
        "unit": "%",
        "description": "Annual dividend yield (as %)",
        "operators": [">", "<", ">=", "<="],
        "requires_history": False,
        "extractor": _extract_per_share,
        "params": {"data_key": "dividend_yield"},
    },
    "red_flag_count": {
        "category": "Fundamental",
        "name": "Red Flag Count",
        "unit": "flags",
        "description": "Number of active danger + warning flags",
        "operators": [">", "<", ">=", "<=", "=="],
        "requires_history": False,
        "extractor": _extract_score,
        "params": {"score_key": "red_flag_count"},
    },
}

# Standard operators — used when the operator doesn't need a previous value
_STANDARD_OPERATORS = {
    ">": _op_gt,
    "<": _op_lt,
    ">=": _op_gte,
    "<=": _op_lte,
    "==": _op_eq,
}

_CROSS_OPERATORS = {
    "crosses_above": _op_crosses_above,
    "crosses_below": _op_crosses_below,
}


def _build_merged_params(signal_def: Dict, condition_params: Dict) -> Dict:
    """Merge signal-level default params with per-condition overrides.

    Signal params come in two styles:
    - Dict-style:  ``{"days": {"type": "int", "default": 1}}``
    - Static:      ``{"score_key": "health_score"}``
    """
    merged = {}
    for k, v in signal_def.get("params", {}).items():
        if isinstance(v, dict):
            default_val = v.get("default", v)
            merged[k] = condition_params.get(k, default_val)
        else:
            merged[k] = condition_params.get(k, v)
    return merged


# ─── Public API ───────────────────────────────────────────────

def get_signal_categories() -> List[str]:
    """Return distinct signal categories in display order."""
    order = ["Price & Volume", "Technical", "Fundamental"]
    return [c for c in order if any(s["category"] == c for s in SIGNAL_CATALOG.values())]


def get_signals_by_category(category: str) -> List[Dict]:
    """Return signal definitions for a given category.

    Strips non-serializable fields (extractor function refs) so the
    output can be safely JSON-serialized for the API.
    """
    result = []
    for sid, sig in SIGNAL_CATALOG.items():
        if sig["category"] == category:
            params = sig.get("params", {})
            result.append({
                "id": sid,
                "signal_id": sid,
                "name": sig["name"],
                "category": sig["category"],
                "unit": sig.get("unit", ""),
                "description": sig.get("description", ""),
                "operators": sig.get("operators", []),
                "value_type": "number",
                "requires_days": bool(
                    sig.get("requires_history", False)
                    and params.get("days")
                ),
                "requires_period": bool(params.get("period")),
            })
    return result


def evaluate_custom_alerts(
    user_id: int, ticker: str, data: Dict, scores: Dict,
    history_override: Optional[pd.DataFrame] = None,
) -> List[Dict]:
    """Evaluate all enabled custom alert rules for a user+ticker.

    Called from checker.py's run_check_for_ticker() after the built-in
    comparisons. Returns a list of notification dicts ready for create_notification().

    When *history_override* is provided (from a reconciliation tick), the
    internal history cache is pre-populated with that DataFrame so no
    redundant yfinance calls are made. In normal mode (the default), a
    fresh cache is created per call.

    Args:
        user_id: The user to evaluate rules for.
        ticker: The stock ticker being checked.
        data: Full fetch_company_data() output dict (normal mode) or a
            minimal dict with at least a ``market`` key (reconciliation mode).
        scores: Flat score dict from checker._compute_scores().
        history_override: Pre-fetched OHLCV DataFrame. Skips yfinance calls.

    Returns:
        List of notification dicts with keys: type, severity, title, body,
        old_value, new_value, rule_id.
    """
    global _history_cache
    if history_override is not None:
        # Reconciliation mode: use pre-fetched data, no cache clear
        _history_cache[ticker] = history_override
    else:
        _history_cache = {}  # fresh cache per check cycle

    rules = get_matching_custom_alert_rules(user_id, ticker, enabled_only=True)
    if not rules:
        return []

    notifications: List[Dict] = []

    for rule in rules:
        try:
            result = _evaluate_single_rule(rule, data, scores, user_id, ticker)
            if result:
                # Hysteresis: don't re-fire while currently_triggered is True.
                # The rule must reset (condition becomes false) before it can
                # fire again. This prevents notification spam for standard
                # operators (>, <, >=, <=, ==, touches_upper, touches_lower).
                if not rule.get("currently_triggered"):
                    update_custom_alert_rule(
                        rule["id"],
                        currently_triggered=1,
                    )
                    notifications.append(result)
            else:
                # Condition not met this cycle — reset trigger state so the
                # rule can fire again when the condition re-activates.
                if rule.get("currently_triggered"):
                    update_custom_alert_rule(
                        rule["id"],
                        currently_triggered=0,
                    )
        except Exception:
            logger.warning(
                f"Custom alert rule '{rule.get('name', rule['id'])}' "
                f"failed for {ticker}",
                exc_info=True,
            )

    return notifications


# ─── Internal: Single Rule Evaluation ─────────────────────────

def _evaluate_single_rule(
    rule: Dict, data: Dict, scores: Dict, user_id: int, ticker: str
) -> Optional[Dict]:
    """Evaluate one custom alert rule. Returns a notification dict or None."""
    conditions = json.loads(rule.get("conditions", "[]"))
    if not conditions:
        return None

    logic_op = rule.get("logic_operator", "AND")
    history: Optional[pd.DataFrame] = None  # lazy loaded

    results: List[bool] = []
    condition_descriptions: List[str] = []
    condition_details: List[tuple] = []

    for cond in conditions:
        signal_id = cond.get("signal_id") or cond.get("signal", "")
        operator = cond.get("operator", "")
        threshold = cond.get("value")
        params = cond.get("params", {})

        signal_def = SIGNAL_CATALOG.get(signal_id)
        if not signal_def:
            logger.warning(f"Unknown signal '{signal_id}' in rule {rule['id']}")
            continue

        # Lazy-load OHLCV history if any condition needs it
        if signal_def.get("requires_history") and history is None:
            history = _get_history(ticker)

        # Merge signal-level params with condition overrides
        merged_params = _build_merged_params(signal_def, params)

        # Extract current value
        extractor = signal_def["extractor"]
        try:
            current_value = extractor(data, scores, (history if history is not None else pd.DataFrame()), merged_params)
        except Exception:
            logger.debug(f"Extractor for '{signal_id}' failed on {ticker}", exc_info=True)
            current_value = None

        if current_value is None or (isinstance(current_value, float) and pd.isna(current_value)):
            logger.debug(f"Signal '{signal_id}' returned None/NaN for {ticker}")
            continue

        # Evaluate condition
        if operator in _CROSS_OPERATORS:
            previous_value = get_custom_alert_snapshot(user_id, ticker, signal_id)
            if previous_value is None:
                # First check — baseline stored at end; skip this condition
                continue
            matched = _CROSS_OPERATORS[operator](current_value, previous_value, threshold)
        elif operator == "touches_upper":
            matched = current_value >= 1.0
        elif operator == "touches_lower":
            matched = current_value <= 0.0
        elif operator in _STANDARD_OPERATORS:
            matched = _STANDARD_OPERATORS[operator](current_value, threshold)
        else:
            logger.warning(f"Unknown operator '{operator}' in rule {rule['id']}")
            continue

        results.append(matched)
        condition_descriptions.append(
            _format_condition(signal_def, operator, threshold, current_value)
        )
        condition_details.append(
            (signal_id, operator, threshold, current_value, cond.get("params", {}), signal_def)
        )

    # Save current values for ALL conditions (for next cycle's crosses detection)
    for cond in conditions:
        signal_id = cond.get("signal_id", "") or cond.get("signal", "")
        signal_def = SIGNAL_CATALOG.get(signal_id)
        if not signal_def:
            continue
        params = cond.get("params", {})
        merged_params = _build_merged_params(signal_def, params)

        try:
            val = signal_def["extractor"](data, scores, (history if history is not None else pd.DataFrame()), merged_params)
            if val is not None and not (isinstance(val, float) and pd.isna(val)):
                save_custom_alert_snapshot(user_id, ticker, signal_id, val)
        except Exception:
            pass

    if not results:
        return None

    # Combine results with AND/OR
    triggered = all(results) if logic_op == "AND" else any(results)
    if not triggered:
        return None

    # Build notification body
    rule_name = rule.get("name", f"Rule #{rule['id']}")
    severity = rule.get("severity", "info")

    if len(condition_details) == 1:
        # Single condition: descriptive natural language
        sid, op, thresh, cur_val, cond_params, sig_def = condition_details[0]
        current_price = data.get("market", {}).get("price")
        body = _format_natural_body(sid, op, thresh, cur_val, cond_params, current_price)
    else:
        # Multiple conditions: join descriptions naturally
        connector = " and " if logic_op == "AND" else " or "
        body = connector.join(condition_descriptions)

    # Collect current values for the notification payload
    value_map = {}
    for cond in conditions:
        sid = cond.get("signal_id", "")
        sd = SIGNAL_CATALOG.get(sid)
        if not sd:
            continue
        cp = cond.get("params", {})
        mp = _build_merged_params(sd, cp)
        try:
            cv = sd["extractor"](data, scores, (history if history is not None else pd.DataFrame()), mp)
            if cv is not None:
                value_map[sid] = round(cv, 2)
        except Exception:
            pass

    return {
        "type": "custom_alert",
        "severity": severity,
        "title": f"⚡ {rule_name}",
        "body": body,
        "old_value": "",
        "new_value": json.dumps(value_map),
        "rule_id": rule["id"],
    }


# ─── Internal: Formatting ─────────────────────────────────────

_OPERATOR_DISPLAY = {
    ">": ">",
    "<": "<",
    ">=": "≥",
    "<=": "≤",
    "==": "=",
    "crosses_above": "crossed above",
    "crosses_below": "crossed below",
    "touches_upper": "touched upper band",
    "touches_lower": "touched lower band",
}


def _format_condition(
    signal_def: Dict, operator: str, threshold: float, current_value: float
) -> str:
    """Convert a condition to human-readable text like 'Price > $150'."""
    name = signal_def.get("name", "?")
    unit = signal_def.get("unit", "")

    if operator in ("touches_upper", "touches_lower"):
        return f"{name} {_OPERATOR_DISPLAY[operator]}"

    op_display = _OPERATOR_DISPLAY.get(operator, operator)

    # Format threshold with unit
    if unit in ("USD", "$"):
        th_str = f"${threshold:,.2f}"
    elif unit == "%":
        th_str = f"{threshold}%"
    elif unit == "×":
        th_str = f"{threshold}×"
    elif unit == "pts":
        th_str = f"{threshold} pts"
    elif unit == "flags":
        th_str = f"{int(threshold)} flags"
    else:
        th_str = f"{threshold:,.2f}"

    # Format current value
    if isinstance(current_value, float):
        cv_str = f"{current_value:,.2f}"
    else:
        cv_str = str(current_value)

    return f"{name} {op_display} {th_str} (now: {cv_str})"


def _format_natural_body(
    signal_id: str,
    operator: str,
    threshold: float,
    current_value: float,
    params: Dict,
    current_price: Optional[float] = None,
) -> str:
    """Generate natural language body text for a single-condition custom alert.

    Produces action-oriented text like:
        "Price dropped 7.2% — below your 5% threshold. Currently at $173.40."
        "RSI at 24.3 — below your 30 threshold (oversold territory)."
        "MACD crossed above signal line — bullish signal."
    """
    signal_def = SIGNAL_CATALOG.get(signal_id, {})
    name = signal_def.get("name", "?")
    unit = signal_def.get("unit", "")

    # --- Format threshold for display ---
    if threshold is not None:
        try:
            threshold = float(threshold)
        except (ValueError, TypeError):
            pass

    if isinstance(threshold, float):
        if unit in ("USD", "$"):
            th_str = f"${threshold:,.2f}"
        elif unit == "%":
            th_str = f"{threshold}%"
        elif unit == "×":
            th_str = f"{threshold}×"
        elif unit == "pts":
            th_str = f"{threshold} pts"
        elif unit == "flags":
            th_str = f"{int(threshold)} flags"
        else:
            th_str = f"{threshold:.2f}"
    else:
        th_str = str(threshold)

    # --- Format current value for display ---
    if isinstance(current_value, float):
        if unit in ("USD", "$"):
            cv_str = f"${current_value:,.2f}"
        elif unit == "%":
            cv_str = f"{current_value:+.1f}%"
        elif unit == "×":
            cv_str = f"{current_value:.1f}×"
        elif unit == "pts":
            cv_str = f"{current_value:.1f} pts"
        else:
            cv_str = f"{current_value:.2f}"
    else:
        cv_str = str(current_value)

    # --- Signal-specific natural language ---
    # Price & Volume
    if signal_id == "price_change_pct":
        if current_value < 0:
            body = f"Price dropped {abs(current_value):.1f}% — below your {abs(threshold):.1f}% threshold."
        else:
            body = f"Price rose {current_value:.1f}% — above your {threshold:.1f}% threshold."
        if current_price is not None:
            body += f" Currently at ${current_price:.2f}."
        return body

    if signal_id == "price_change_abs":
        direction = "dropped" if current_value < 0 else "rose"
        body = f"Price {direction} ${abs(current_value):.2f} — past your ${abs(threshold):.2f} threshold."
        if current_price is not None:
            body += f" Currently at ${current_price:.2f}."
        return body

    if signal_id == "price":
        below = operator in ("<", "<=")
        body = f"Price at {cv_str} — {'below' if below else 'above'} your {th_str} threshold."
        return body

    if signal_id == "distance_52w_high":
        body = f"Price is {current_value:.1f}% below 52-week high (threshold: {th_str})."
        return body

    if signal_id == "distance_52w_low":
        body = f"Price is {current_value:.1f}% above 52-week low (threshold: {th_str})."
        return body

    if signal_id == "volume_spike":
        return f"Volume is {cv_str} average — unusual activity detected."

    # Technical
    if signal_id == "rsi":
        below = operator in ("<", "<=")
        zone = "oversold" if below else "overbought"
        return (
            f"RSI at {current_value:.1f} — {'below' if below else 'above'} "
            f"your {threshold:.0f} threshold ({zone} territory)."
        )

    if signal_id == "sma_crossover":
        period = params.get("period", 50)
        if operator == "crosses_above":
            return f"Price crossed above {period}-day SMA — bullish signal."
        else:
            return f"Price crossed below {period}-day SMA — bearish signal."

    if signal_id == "macd":
        sig = operator == "crosses_above"
        return f"MACD crossed {'above' if sig else 'below'} signal line — {'bullish' if sig else 'bearish'} signal."

    if signal_id == "bollinger":
        if operator == "touches_upper":
            return "Price touched upper Bollinger Band — overextended."
        else:
            return "Price touched lower Bollinger Band — potential bounce zone."

    # Fundamental / Generic fallback
    below = operator in ("<", "<=")
    return f"{name} is {cv_str} — {'below' if below else 'above'} your {th_str} threshold."


def describe_condition_for_ui(cond: Dict) -> str:
    """Return a short human-readable description of a condition for the UI.

    Used in the rule list cards to summarize each condition without live data.
    """
    signal_id = cond.get("signal_id", "") or cond.get("signal", "")
    operator = cond.get("operator", "")
    threshold = cond.get("value")
    signal_def = SIGNAL_CATALOG.get(signal_id, {})

    name = signal_def.get("name", signal_id)
    unit = signal_def.get("unit", "")

    if operator in ("touches_upper", "touches_lower"):
        return f"{name} {_OPERATOR_DISPLAY.get(operator, operator)}"

    op_display = _OPERATOR_DISPLAY.get(operator, operator)

    if unit in ("USD", "$"):
        th_str = f"${threshold:,.2f}"
    elif unit == "%":
        th_str = f"{threshold}%"
    elif unit == "×":
        th_str = f"{threshold}×"
    elif unit == "pts":
        th_str = f"{threshold} pts"
    elif unit == "flags":
        th_str = f"{int(threshold)} flags"
    else:
        th_str = str(threshold)

    # Include extra params in description
    params = cond.get("params", {})
    extras = []
    if "days" in params and params["days"] != 5:
        extras.append(f"{params['days']}d")
    if "period" in params and params["period"] != 50:
        extras.append(f"SMA{params['period']}")

    suffix = f" ({', '.join(extras)})" if extras else ""
    return f"{name} {op_display} {th_str}{suffix}"
