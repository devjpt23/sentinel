"""
Notification checker engine.

Compares current scores against previous snapshots and generates notifications
when meaningful changes are detected. Designed to run both from the background
scheduler and from the CLI tool.

Every function returns plain dicts/lists — no classes, consistent with the
rest of the Sentinel codebase.
"""

import hashlib
import json
import logging
import re
import threading
import time
from typing import Optional, List, Dict

import pandas as pd

from src.data.fetcher import fetch_company_data, _fetch_news, _get_ticker
from src.data.notification_db import (
    get_latest_snapshot,
    save_snapshot,
    create_notification,
    update_check_log,
    get_preferences,
    mark_delivered,
    get_custom_alert_rule_by_id,
    get_all_active_alerts_grouped_by_ticker,
    insert_news_article,
    count_unnotified_news,
    get_unnotified_articles,
    mark_articles_notified,
    mark_old_news_skipped,
    purge_old_news_entries,
    get_tickers_with_unnotified_news,
    count_news_title_hash,
)
from src.data.push_db import get_all_active_subscriptions
from src.data.watchlist_db import load_user_watchlist
from src.notifications.custom_alerts import evaluate_custom_alerts
from src.notifications.telegram_bot import (
    send_telegram_message,
    format_telegram_notification,
)
from src.notifications.push_sender import send_push_notifications

logger = logging.getLogger(__name__)

_news_check_lock = threading.Lock()
_news_error_counts: Dict[str, int] = {}  # ticker -> consecutive failures
_last_news_cleanup = 0.0


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

    # 5c. Add current price context to all notifications for push formatting
    current_price = data.get("market", {}).get("price")
    for n in notifications:
        n["current_price"] = current_price

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


def evaluate_price_alert(
    user_id: int, ticker: str, price: float
) -> List[Dict]:
    """Evaluate custom alert rules for a ticker using only the current price.

    Bypasses full yfinance fetch. Creates a minimal data dict with just the
    price so that ``_extract_price`` fires but OHLCV-backed extractors (RSI,
    MACD, Bollinger, SMA crossover, price change %, volume spike) return
    None and are skipped. Fundamental and news signals also return None/0.

    Designed for the Finnhub real-time price feed path. Returns the same
    format as ``run_check_for_ticker()``.

    Args:
        user_id: The user whose rules to evaluate.
        ticker: The stock ticker symbol.
        price: The current trade price.

    Returns:
        List of notification dicts (empty if no rules matched).
    """
    data = {"market": {"price": price}}
    notifications = evaluate_custom_alerts(
        user_id, ticker, data, {},
        history_override=pd.DataFrame(),
    )
    if notifications:
        for n in notifications:
            n["current_price"] = price
    return notifications


def format_push_notification(
    notification: Dict,
) -> tuple:
    """Format a notification dict for push delivery.

    Strips the ticker prefix from the body (already in the title),
    wraps to 120 chars, and extracts a structured data payload.

    Returns (title, body, extra_data_dict).
    """
    title = notification.get("title", "Alert")
    body = notification.get("body", "") or ""
    ticker = notification.get("ticker", "")

    # Strip ticker prefix from body if present (custom alerts include it)
    if ticker:
        body = re.sub(rf"^{re.escape(ticker)}:\s*", "", body)

    # For custom alerts, add current price context
    if notification.get("type") == "custom_alert":
        price = notification.get("current_price")
        if price is not None:
            price_context = f" | Price: ${float(price):.2f}"
            if price_context not in body:
                body += price_context

    # Wrap to 120 chars
    if len(body) > 120:
        body = body[:117] + "..."

    # Build extra data payload
    extra_data = {}
    price = notification.get("current_price")
    if price is not None:
        extra_data["current_price"] = round(float(price), 2)

    return title, body, extra_data


def deliver_notifications(user_id: int, notifications_by_ticker: Dict[str, List[Dict]]) -> int:
    """Deliver notifications via Telegram and Web Push. Returns total delivered count."""
    prefs = get_preferences(user_id)
    delivered = 0

    # ── Collect affected user_ids and batch-fetch push subs ──
    # (For current single-user flow this is just [user_id], but batch-fetching
    # prevents N+1 queries when the daemon scales to multi-user delivery cycles.)
    push_subs_by_user = get_all_active_subscriptions([user_id])
    user_push_subs = push_subs_by_user.get(user_id, [])

    # ── Push channel ──
    if user_push_subs and prefs.get("push_enabled", 1):
        for _ticker, notifications in notifications_by_ticker.items():
            for n in notifications:
                rule_id = n.get("rule_id")
                if not rule_id:
                    continue
                rule = get_custom_alert_rule_by_id(rule_id)
                if rule and rule.get("fire_push", 1):
                    title, body, extra_data = format_push_notification(n)
                    results = send_push_notifications(
                        subscriptions=user_push_subs,
                        title=title,
                        body=body,
                        data={
                            "ticker": n.get("ticker"),
                            "rule_id": rule_id,
                            "notification_id": n.get("id"),
                            "url": f"/company/{n.get('ticker', '')}",
                            "severity": n.get("severity"),
                            "notification_type": n.get("type"),
                            **extra_data,
                        },
                    )
                    for r in results:
                        if r["status"] == "sent":
                            delivered += 1

    # ── Telegram channel ──
    bot_token = prefs.get("telegram_bot_token", "")
    telegram_enabled = (
        bool(prefs.get("telegram_enabled"))
        and bool(prefs.get("telegram_chat_id"))
        and bool(bot_token)
    )

    for _ticker, notifications in notifications_by_ticker.items():
        for n in notifications:
            if not telegram_enabled:
                continue
            # Per-rule Telegram gate: if the rule has fire_telegram=0, skip
            rule_id = n.get("rule_id")
            if rule_id:
                rule = get_custom_alert_rule_by_id(rule_id)
                if rule and not rule.get("fire_telegram", 1):
                    continue
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

    delta_val = abs(delta)
    if delta < 0:
        body = (
            f"Score dropped from {old_score} ({old_verdict}) → {new_score} ({new_verdict}) "
            f"— a {delta_val}-point decline. Review financial health in the dashboard."
        )
    else:
        body = (
            f"Score improved from {old_score} ({old_verdict}) → {new_score} ({new_verdict}) "
            f"— a {delta_val}-point gain."
        )

    return {
        "type": "health_change",
        "severity": severity,
        "title": f"Health Score {direction} {emoji}",
        "body": body,
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

    if new_count > old_count:
        body = (
            f"{new_count} new red flags detected (was {old_count}). "
            f"Check the Risk Analysis page for details on each flag."
        )
    else:
        body = (
            f"Red flags decreased from {old_count} to {new_count}. "
            f"Risk posture is improving."
        )

    return {
        "type": "risk_flag_change",
        "severity": severity,
        "title": f"Red Flags {direction} {emoji}",
        "body": body,
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
        body = (
            f"Z-Score shifted from {old_zone} ({old_z}) → {new_zone} ({new_z}). "
            f"Bankruptcy risk is elevated — review leverage and liquidity."
        )
    else:
        severity = "info"
        direction = "Improved"
        emoji = "✅"
        body = (
            f"Z-Score shifted from {old_zone} ({old_z}) → {new_zone} ({new_z}). "
            f"Bankruptcy risk is decreasing."
        )

    return {
        "type": "zscore_zone_change",
        "severity": severity,
        "title": f"Z-Score Zone {direction} {emoji}",
        "body": body,
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

    if delta < 0:
        body = (
            f"F-Score declined from {old_fs}/9 → {new_fs}/9 ({delta:+d} points). "
            f"Financial strength is weakening."
        )
    else:
        body = (
            f"F-Score improved from {old_fs}/9 → {new_fs}/9 (+{delta} points). "
            f"Financial strength is getting better."
        )

    return {
        "type": "fscore_change",
        "severity": severity,
        "title": f"Piotroski F-Score {direction} {emoji}",
        "body": body,
        "old_value": str(old_fs),
        "new_value": str(new_fs),
    }


# ─── News Check ─────────────────────────────────────────────────


# ─── Sector Peer Helpers (for industry-level news) ──────────────


def get_sector_peer_tickers(user_id: int, max_per_sector: int = 2) -> List[str]:
    """Get representative tickers from sectors matching a user's watchlist.

    Used by the ``new_industry_news`` signal. Picks up to *max_per_sector*
    tickers per sector that the user doesn't already watch, so the signal
    can surface relevant industry news the user might miss.

    Returns an empty list when the universe isn't loaded, when the
    watchlist is empty, or when all peer candidates are already watched.
    """
    from src.data.sector_universe import load_universe, get_companies_in_sector
    from src.data.watchlist_db import load_user_watchlist

    watchlist = load_user_watchlist(user_id)
    if not watchlist:
        return []

    universe = load_universe()
    ticker_to_sector: Dict[str, str] = {}
    for c in universe:
        s = c.get("sector")
        if s:
            ticker_to_sector[c["ticker"]] = s

    user_sectors: set = set()
    for t in watchlist:
        if t in ticker_to_sector:
            user_sectors.add(ticker_to_sector[t])

    watchlist_set = set(watchlist)
    peers: List[str] = []
    for sector in sorted(user_sectors):
        companies = get_companies_in_sector(sector)
        candidates = [
            c["ticker"] for c in companies
            if c["ticker"] not in watchlist_set
        ]
        peers.extend(candidates[:max_per_sector])

    return peers


def check_ticker_news() -> int:
    """Check for new news on tickers with active new_news alert rules.

    Fetches news in batches (5 tickers per batch, 1s delay between batches),
    deduplicates by URL hash + title hash, evaluates alert rules, and
    creates notifications for matching articles.

    Also fetches news for sector-peer tickers when any user has a
    ``new_industry_news`` rule, enabling industry-level alerting.

    Returns total notifications generated.
    """
    acquired = _news_check_lock.acquire(blocking=False)
    if not acquired:
        logger.info("News check: previous run still in progress, skipping")
        return 0

    try:
        # Get all active rules grouped by ticker
        rules_by_ticker = get_all_active_alerts_grouped_by_ticker()
        # Filter to tickers that have new_news or new_industry_news signals
        news_tickers: set = set()
        industry_users: set = set()  # users with new_industry_news rules
        for ticker, rules in rules_by_ticker.items():
            for rule in rules:
                conditions = json.loads(rule.get("conditions", "[]"))
                for cond in conditions:
                    sid = cond.get("signal_id") or cond.get("signal", "")
                    if sid == "new_news":
                        news_tickers.add(ticker)
                        break
                    if sid == "new_industry_news":
                        industry_users.add(rule["user_id"])

        # Add sector-peer tickers for users with industry-news rules
        if industry_users:
            for uid in industry_users:
                peers = get_sector_peer_tickers(uid)
                if peers:
                    news_tickers.update(peers)
            logger.debug(
                "News check: %d industry-peer tickers after sector expansion",
                len(news_tickers),
            )

        if not news_tickers:
            logger.debug("News check: no tickers with new_news rules")
            return 0

        logger.info("News check: checking %d tickers", len(news_tickers))

        # Fetch news in batches
        ticker_list = sorted(news_tickers)
        all_articles: Dict[str, list] = {}

        for i in range(0, len(ticker_list), 5):
            batch = ticker_list[i:i + 5]
            for ticker in batch:
                try:
                    t = _get_ticker(ticker)
                    articles = _fetch_news(t)
                    if not articles:
                        _news_error_counts[ticker] = _news_error_counts.get(ticker, 0) + 1
                        if _news_error_counts[ticker] >= 3:
                            logger.warning(
                                "News check: %s failed 3 consecutive times, backing off", ticker
                            )
                        continue

                    _news_error_counts[ticker] = 0  # reset on success
                    all_articles[ticker] = articles

                except Exception as e:
                    _news_error_counts[ticker] = _news_error_counts.get(ticker, 0) + 1
                    logger.debug("News check: error fetching %s: %s", ticker, e)

            if i + 5 < len(ticker_list):
                time.sleep(1)  # delay between batches

        if not all_articles:
            logger.info("News check: no new articles found")
            return 0

        # Deduplicate and insert
        new_count = 0
        for ticker, articles in all_articles.items():
            for article in articles:
                url = article.get("url", "")
                title = article.get("title", "")
                if not url or not title:
                    continue

                article_id = hashlib.sha256(url.encode()).hexdigest()
                title_hash = hashlib.sha256(title.lower().strip().encode()).hexdigest()

                # Secondary dedup: check title hash in last 24h
                if count_news_title_hash(ticker, title_hash, hours=24) > 0:
                    continue

                inserted = insert_news_article(
                    ticker=ticker,
                    article_id=article_id,
                    title_hash=title_hash,
                    url=url,
                    title=title,
                    summary=article.get("summary", ""),
                    publisher=article.get("publisher", ""),
                    published=article.get("published", ""),
                )
                if inserted:
                    new_count += 1

        if new_count == 0:
            logger.debug("News check: all articles already seen")
            return 0

        logger.info(
            "News check: %d new articles across %d tickers",
            new_count, len(all_articles),
        )

        # Now evaluate rules for each (user, ticker) with unnotified articles
        total_notifications = 0
        tickers_with_news = get_tickers_with_unnotified_news()
        news_ticker_set = {t[0] for t in tickers_with_news}
        delivered_articles: Dict[str, list] = {}  # ticker -> article_ids

        for user_id in set(
            r["user_id"] for rules in rules_by_ticker.values() for r in rules
        ):
            for ticker in news_ticker_set:
                if ticker not in rules_by_ticker:
                    continue

                # Check if any rule for this user has new_news signal
                user_rules = [
                    r for r in rules_by_ticker[ticker] if r["user_id"] == user_id
                ]
                if not user_rules:
                    continue

                try:
                    # Provide context so the new_news extractor knows this is a news tick
                    data = {
                        "_ticker": ticker,
                        "_news_check_context": {
                            "news_check_active": True,
                            "_user_id": user_id,
                        },
                    }
                    scores: Dict = {}

                    from src.notifications.custom_alerts import evaluate_custom_alerts

                    notifications = evaluate_custom_alerts(
                        user_id, ticker, data, scores,
                        history_override=pd.DataFrame(),
                    )

                    if notifications:
                        # Get the articles that were delivered
                        articles = get_unnotified_articles(ticker)
                        article_ids = [a["article_id"] for a in articles]

                        if article_ids:
                            for n in notifications:
                                # Override notification with news content
                                article = articles[0] if articles else None
                                if article:
                                    n["type"] = "news"
                                    n["title"] = (
                                        f"{article['publisher']}: {article['title']}"[:120]
                                        if article.get("publisher")
                                        else article["title"]
                                    )
                                    n["body"] = article.get("summary", "")[:120]
                                    n["url"] = article.get("url", "")
                                    n["ticker"] = ticker

                                nid = create_notification(
                                    user_id=user_id,
                                    ticker=ticker,
                                    notification_type=n.get("type", "news"),
                                    severity=n.get("severity", "info"),
                                    title=n.get("title", ""),
                                    body=n.get("body", ""),
                                    new_value=n.get("url", ""),
                                )
                                n["id"] = nid
                                n["ticker"] = ticker

                            total_notifications += len(notifications)
                            deliver_notifications(user_id, {ticker: notifications})
                            # Track articles for batch marking after all users
                            delivered_articles.setdefault(ticker, []).extend(article_ids)

                except Exception:
                    logger.warning(
                        "News check: rule evaluation failed for user %d, %s",
                        user_id, ticker, exc_info=True,
                    )

        # Mark articles as notified for ALL users at the end
        for ticker, article_ids in delivered_articles.items():
            mark_articles_notified(ticker, article_ids)

        # Mark old unnotified articles as skipped (24h safety limit)
        skipped = mark_old_news_skipped(hours=24)
        if skipped:
            logger.debug("News check: marked %d stale articles as skipped", skipped)

        # Daily cleanup
        global _last_news_cleanup
        if time.time() - _last_news_cleanup > 86400:
            purged = purge_old_news_entries(days=7)
            logger.info("News check: purged %d old news entries", purged)
            _last_news_cleanup = time.time()

        return total_notifications

    finally:
        _news_check_lock.release()
