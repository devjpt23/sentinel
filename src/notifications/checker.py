"""
Notification checker engine.

Compares current scores against previous snapshots and generates notifications
when meaningful changes are detected. Designed to run both from the background
scheduler and from the CLI tool.

Every function returns plain dicts/lists — no classes, consistent with the
rest of the Sentinel codebase.
"""

import logging
from typing import Optional, List, Dict

from src.data.fetcher import fetch_company_data
from src.data.notification_db import (
    get_latest_snapshot,
    save_snapshot,
    create_notification,
    update_check_log,
    get_preferences,
    mark_delivered,
)
from src.data.watchlist_db import load_user_watchlist
from src.notifications.custom_alerts import evaluate_custom_alerts
from src.notifications.telegram_bot import (
    send_telegram_message,
    format_telegram_notification,
)

logger = logging.getLogger(__name__)


# ─── Main Check Entry Points ─────────────────────────────────

def run_check_for_ticker(user_id: int, ticker: str) -> List[Dict]:
    """Fetch data, score, compare against snapshot, generate notifications.

    Returns list of notification dicts created (empty if no changes).
    """
    # 1. Fetch current data (benefits from existing disk/memory cache)
    try:
        data = fetch_company_data(ticker)
    except Exception as e:
        logger.warning(f"Failed to fetch data for {ticker}: {e}")
        return []

    if data is None:
        return []

    # 2. Compute all scores
    current = _compute_scores(data)

    # 3. Get previous snapshot
    previous = get_latest_snapshot(user_id, ticker)

    # 4. If no snapshot yet, create baseline (no notifications)
    if previous is None:
        save_snapshot(user_id, ticker, current)
        update_check_log(user_id, ticker)
        return []

    # 5. Compare and generate notifications
    notifications = []
    prefs = get_preferences(user_id)

    comparisons = [
        (_compare_health, "health_change"),
        (_compare_verdicts, "verdict_change"),
        (_compare_risk_flags, "risk_flag_change"),
        (_compare_zscore, "zscore_zone_change"),
        (_compare_fscore, "fscore_change"),
    ]

    for compare_fn, pref_key in comparisons:
        if prefs.get(pref_key, 1):  # enabled by default
            result = compare_fn(previous, current, ticker, prefs)
            if result:
                nid = create_notification(
                    user_id=user_id,
                    ticker=ticker,
                    notification_type=result["type"],
                    severity=result["severity"],
                    title=result["title"],
                    body=result.get("body"),
                    old_value=result.get("old_value"),
                    new_value=result.get("new_value"),
                )
                result["ticker"] = ticker
                result["id"] = nid
                notifications.append(result)

    # 5b. Evaluate custom alert rules
    try:
        custom_notifications = evaluate_custom_alerts(user_id, ticker, data, current)
        if custom_notifications:
            for cn in custom_notifications:
                nid = create_notification(
                    user_id=user_id,
                    ticker=ticker,
                    notification_type=cn["type"],
                    severity=cn["severity"],
                    title=cn["title"],
                    body=cn.get("body"),
                    old_value=cn.get("old_value"),
                    new_value=cn.get("new_value"),
                )
                cn["ticker"] = ticker
                cn["id"] = nid
            notifications.extend(custom_notifications)
    except Exception:
        logger.warning(
            f"Custom alert evaluation failed for {ticker}", exc_info=True
        )

    # 6. Save new snapshot + update check log
    save_snapshot(user_id, ticker, current)
    update_check_log(user_id, ticker)

    return notifications


def check_all_tickers_for_user(user_id: int) -> Dict[str, List[Dict]]:
    """Run checks for every ticker in a user's watchlist.

    Returns dict mapping ticker -> list of notification dicts.
    Only includes tickers that generated notifications.
    """
    tickers = load_user_watchlist(user_id)
    results: Dict[str, List[Dict]] = {}

    for ticker in tickers:
        try:
            notifications = run_check_for_ticker(user_id, ticker)
            if notifications:
                results[ticker] = notifications
        except Exception as e:
            logger.exception(f"Error checking {ticker} for user {user_id}: {e}")

    return results


def deliver_notifications(user_id: int, notifications_by_ticker: Dict[str, List[Dict]]) -> int:
    """Deliver all notifications via Telegram. Returns total delivered count.

    Each notification is always stored in-app (DB). Delivery is attempted via
    Telegram if the user has configured and enabled it.
    """
    prefs = get_preferences(user_id)
    delivered = 0

    # ── Telegram channel ────────────────────────────────────
    bot_token = prefs.get("telegram_bot_token", "")
    telegram_enabled = (
        bool(prefs.get("telegram_enabled"))
        and bool(prefs.get("telegram_chat_id"))
        and bool(bot_token)
    )

    for _ticker, notifications in notifications_by_ticker.items():
        for n in notifications:
            if telegram_enabled:
                try:
                    text = format_telegram_notification(n)
                    sent = send_telegram_message(
                        bot_token, prefs["telegram_chat_id"], text
                    )
                    if sent:
                        mark_delivered(n["id"], "telegram")
                        delivered += 1
                except Exception as e:
                    logger.warning(f"Telegram delivery failed for notification {n.get('id')}: {e}")

    return delivered


# ─── Score Computation ───────────────────────────────────────

def _compute_scores(data: Dict) -> Dict:
    """Run all scoring modules on fetched data. Returns a flat snapshot dict."""
    from src.scoring.health import compute_health_score
    from src.scoring.zscore import compute_altman_zscore
    from src.scoring.valuation import compute_price_verdict
    from src.scoring.intrinsic import compute_intrinsic_worth
    from src.scoring.risk import compute_risk_assessment, compute_red_flags

    # Health + F-Score (also computes Z-Score internally, but we recompute for isolation)
    health_score, health_verdict, fscore, _ = compute_health_score(data)

    # Z-Score (standalone, for snapshot and risk)
    z_score, z_zone, _ = compute_altman_zscore(data)

    # Price vs Peers (pass empty peer_averages — peer comparison is optional)
    _, price_verdict, _, _ = compute_price_verdict(data, {})

    # Intrinsic Worth
    _, intrinsic_verdict, _, _, _ = compute_intrinsic_worth(data)

    # Risk
    risk_score, risk_label, _, risk_factors = compute_risk_assessment(data, z_score, z_zone)
    red_flags = compute_red_flags(data, risk_factors)

    return {
        "health_score": health_score,
        "health_verdict": health_verdict,
        "fscore": fscore,
        "risk_label": risk_label,
        "risk_score": risk_score,
        "red_flag_count": len([f for f in red_flags if f[0] == "danger"]) if red_flags else 0,
        "price_verdict": price_verdict,
        "intrinsic_verdict": intrinsic_verdict,
        "zscore": round(z_score, 2) if z_score else None,
        "zscore_zone": z_zone,
    }


# ─── Comparison Functions ────────────────────────────────────

def _compare_health(
    previous: Dict, current: Dict, _ticker: str, prefs: Dict
) -> Optional[Dict]:
    """Check for significant health score changes."""
    old_score = previous.get("health_score")
    new_score = current.get("health_score")

    if old_score is None or new_score is None:
        return None

    delta = new_score - old_score
    min_delta = prefs.get("min_health_delta", 15)

    if abs(delta) < min_delta:
        return None

    # Determine severity
    if delta < 0:
        severity = "critical" if abs(delta) >= 30 else "warning"
        direction = "Declined"
        emoji = "📉"
    else:
        severity = "info"
        direction = "Improved"
        emoji = "📈"

    old_verdict = previous.get("health_verdict", "?")
    new_verdict = current.get("health_verdict", "?")

    return {
        "type": "health_change",
        "severity": severity,
        "title": f"Health Score {direction} {emoji}",
        "body": (
            f"Score changed from {old_score} ({old_verdict}) to {new_score} ({new_verdict}). "
            f"The composite health score reflects profitability, leverage, and efficiency."
        ),
        "old_value": str(old_score),
        "new_value": str(new_score),
    }


def _compare_verdicts(
    previous: Dict, current: Dict, _ticker: str, _prefs: Dict
) -> Optional[Dict]:
    """Check for valuation verdict changes (price or intrinsic)."""
    old_price = previous.get("price_verdict", "")
    new_price = current.get("price_verdict", "")
    old_intrinsic = previous.get("intrinsic_verdict", "")
    new_intrinsic = current.get("intrinsic_verdict", "")

    changes = []
    if old_price != new_price:
        changes.append(f"Price verdict: {old_price} → {new_price}")
    if old_intrinsic != new_intrinsic:
        changes.append(f"Intrinsic worth: {old_intrinsic} → {new_intrinsic}")

    if not changes:
        return None

    severity = "info"
    direction = "Shifted"
    if old_price and new_price:
        # Price verdict improvement
        price_order = ["Overvalued", "Fairly Valued", "Undervalued"]
        try:
            old_idx = price_order.index(old_price)
            new_idx = price_order.index(new_price)
            direction = "Improved 📈" if new_idx > old_idx else "Declined 📉"
            severity = "warning" if new_idx < old_idx else "info"
        except ValueError:
            pass

    return {
        "type": "verdict_change",
        "severity": severity,
        "title": f"Valuation Verdict {direction}",
        "body": " | ".join(changes),
        "old_value": f"P:{old_price} I:{old_intrinsic}",
        "new_value": f"P:{new_price} I:{new_intrinsic}",
    }


def _compare_risk_flags(
    previous: Dict, current: Dict, _ticker: str, _prefs: Dict
) -> Optional[Dict]:
    """Check for changes in red flag count."""
    old_count = previous.get("red_flag_count", 0) or 0
    new_count = current.get("red_flag_count", 0) or 0

    if old_count == new_count:
        return None

    if new_count > old_count:
        severity = "warning"
        direction = "Increased"
        emoji = "⚠️"
    else:
        severity = "info"
        direction = "Decreased"
        emoji = "✅"

    return {
        "type": "risk_flag_change",
        "severity": severity,
        "title": f"Red Flags {direction} {emoji}",
        "body": (
            f"Red flag count changed from {old_count} to {new_count}. "
            f"Red flags are automated checks for financial distress, "
            f"accounting concerns, and operational weakness."
        ),
        "old_value": str(old_count),
        "new_value": str(new_count),
    }


def _compare_zscore(
    previous: Dict, current: Dict, _ticker: str, _prefs: Dict
) -> Optional[Dict]:
    """Check for Z-Score zone transitions (Safe ↔ Grey ↔ Distress)."""
    old_zone = previous.get("zscore_zone", "")
    new_zone = current.get("zscore_zone", "")
    old_z = previous.get("zscore")
    new_z = current.get("zscore")

    if not old_zone or not new_zone or old_zone == new_zone:
        return None

    zone_order = ["Distress", "Grey", "Safe"]
    try:
        old_idx = zone_order.index(old_zone)
        new_idx = zone_order.index(new_zone)
    except ValueError:
        return None

    if new_idx < old_idx:
        severity = "warning"
        direction = "Worsened"
        emoji = "⚠️"
    else:
        severity = "info"
        direction = "Improved"
        emoji = "✅"

    return {
        "type": "zscore_zone_change",
        "severity": severity,
        "title": f"Z-Score Zone {direction} {emoji}",
        "body": (
            f"Altman Z-Score zone changed from {old_zone} ({old_z}) to "
            f"{new_zone} ({new_z}). The Z-Score measures bankruptcy risk "
            f"using leverage, liquidity, profitability, and market value."
        ),
        "old_value": f"{old_zone} ({old_z})",
        "new_value": f"{new_zone} ({new_z})",
    }


def _compare_fscore(
    previous: Dict, current: Dict, _ticker: str, _prefs: Dict
) -> Optional[Dict]:
    """Check for Piotroski F-Score changes (≥3 points)."""
    old_fs = previous.get("fscore")
    new_fs = current.get("fscore")

    if old_fs is None or new_fs is None:
        return None

    delta = new_fs - old_fs
    if abs(delta) < 3:
        return None

    if delta < 0:
        severity = "warning"
        direction = "Declined"
        emoji = "📉"
    else:
        severity = "info"
        direction = "Improved"
        emoji = "📈"

    return {
        "type": "fscore_change",
        "severity": severity,
        "title": f"Piotroski F-Score {direction} {emoji}",
        "body": (
            f"F-Score changed from {old_fs}/9 to {new_fs}/9 (Δ {delta:+d}). "
            f"The Piotroski F-Score rates financial strength across 9 criteria: "
            f"profitability, leverage/liquidity, and operating efficiency."
        ),
        "old_value": str(old_fs),
        "new_value": str(new_fs),
    }
