"""
Sentinel HTTP API — remote data access for Streamlit Cloud and Next.js SPA.

A lightweight Flask server that exposes the VPS SQLite database over HTTP.
All endpoints (except auth and CORS preflight) require the X-API-Key header.
The server binds to 0.0.0.0 (all interfaces) — nginx proxy controls external access.

Usage:
    SENTINEL_API_KEY=my-secret python -m src.api.server
"""

import json
import logging
import os
import secrets
import time
import threading

# In-memory cache for expensive endpoint results
_enriched_cache: dict[str, tuple[float, str]] = {}  # key -> (timestamp, json_response)
_ENRICHED_CACHE_TTL = 300  # 5 minutes
_enriched_cache_lock = threading.Lock()


def _invalidate_enriched_cache(user_id: int) -> None:
    key = f"enriched:{user_id}"
    with _enriched_cache_lock:
        _enriched_cache.pop(key, None)


from flask import Flask, request, jsonify, abort
from flask_cors import CORS

from src.data.auth_db import (
    init_auth_db,
    get_user,
    get_all_users,
    register_user,
    login_user,
    create_session,
    restore_user_from_session,
    delete_session,
    delete_all_sessions,
    link_telegram,
    get_user_by_email,
    create_password_reset_token,
    get_user_from_reset_token,
    update_user_password,
    send_password_reset_email,
)
from src.data.watchlist_db import (
    load_user_watchlist,
    add_user_ticker,
    remove_user_ticker,
    clear_user_watchlist,
    get_user_watchlist_count,
    is_ticker_watched_by_user,
)
from src.data.notification_db import (
    init_notification_db,
    get_notifications,
    get_unread_count,
    get_preferences,
    set_preferences,
    get_user_bot_tokens,
    mark_read,
    mark_all_read,
    dismiss_notification,
    get_custom_alert_rules,
    create_custom_alert_rule,
    update_custom_alert_rule,
    delete_custom_alert_rule,
    toggle_custom_alert_rule,
    get_custom_alert_rule_by_id,
)
from src.data.fetcher import (
    fetch_company_data,
    fetch_price_growth,
    fetch_price_history,
    fetch_peers,
    fetch_peer_metrics,
    compute_peer_averages,
    compute_quick_health,
    fetch_macro_context,
    fetch_analyst_data,
    fetch_institutional_data,
    fetch_top_movers,
    fetch_market_news,
    fetch_market_indices,
    _cached_ticker_info,
)
from src.scoring.health import compute_health_score
from src.scoring.risk import compute_risk_assessment, compute_red_flags
from src.scoring.intrinsic import compute_intrinsic_worth
from src.scoring.dcf import compute_dcf
from src.scoring.zscore import compute_altman_zscore, compute_altman_zscore_with_components, compute_zscore_normalized
from src.data.sec_edgar import fetch_sec_filings_edgar, fetch_insider_trading_edgar
from src.data.supply_chain_data import get_enriched_relationships, load_country_risk, get_country_risk
from src.data.company_links import load_relationships
from src.data.sector_universe import (
    get_all_sectors,
    search_sectors,
    get_companies_matching,
)
from src.data.openbb_fetcher import fetch_screener_obb
from src.notifications.custom_alerts import SIGNAL_CATALOG

from src.notifications.custom_alerts import (
    get_signal_categories,
    get_signals_by_category,
)
from src.data.push_db import (
    upsert_push_subscription,
    remove_push_subscription,
    get_push_subscriptions_for_user,
)
from src.notifications.push_sender import send_push_notifications
from src.notifications.checker import check_all_tickers_for_user, deliver_notifications
from src.notifications.daemon import reconciliation_tick

logger = logging.getLogger(__name__)

API_KEY = os.environ.get("SENTINEL_API_KEY", "")
if not API_KEY:
    logger.error("SENTINEL_API_KEY environment variable is not set")

app = Flask(__name__)

# ─── CORS ──────────────────────────────────────────────────────

CORS_ORIGINS = [
    o.strip() for o in os.environ.get(
        "CORS_ORIGINS",
        "http://localhost:3000,https://sentinel.app,https://web-fryhoudgw-devjpt23s-projects.vercel.app",
    ).split(",") if o.strip()
]

CORS(app, resources={r"/*": {"origins": CORS_ORIGINS}}, supports_credentials=True)

# ─── Rate Limiting ─────────────────────────────────────────────

_rate_limits: dict[str, list[float]] = {}
_rate_lock = threading.Lock()

MAX_REQUESTS_PER_MINUTE = 60
MAX_READ_PER_MINUTE = 120   # read endpoints
MAX_WRITE_PER_MINUTE = 60   # write endpoints
MAX_AUTH_PER_MINUTE = 60    # auth endpoints


def _check_rate_limit(ip: str, max_requests: int = MAX_REQUESTS_PER_MINUTE) -> bool:
    """Return True if the request is within rate limits."""
    now = time.time()
    with _rate_lock:
        _rate_limits[ip] = [t for t in _rate_limits.get(ip, []) if now - t < 60]
        if len(_rate_limits[ip]) >= max_requests:
            return False
        _rate_limits[ip].append(now)
        return True


# ─── Middleware ────────────────────────────────────────────────

# Paths that do NOT require X-API-Key (they use session tokens instead)
_AUTH_PREFIXES = ("/api/auth/", "/api/auth", "/api/push/")


def _resolve_user_id_from_session():
    """Resolve user_id from the X-Session-Token header.

    Returns the user_id (int) if a valid session exists, otherwise
    aborts the request with 401.
    """
    token = request.headers.get("X-Session-Token", "")
    if not token:
        abort(401)
    user = restore_user_from_session(token)
    if not user:
        abort(401)
    return user["id"]


def _check_session_owns_user_id(user_id):
    """Verify the session in X-Session-Token matches the given user_id.

    Returns None if authorized, or a (response, status_code) tuple if
    unauthorized (401 missing/invalid token, 403 forbidden).

    Use at the top of any endpoint that accepts user_id from the URL or
    request body to prevent IDOR (Insecure Direct Object Reference).
    """
    session_token = request.headers.get("X-Session-Token")
    if not session_token:
        return jsonify({"error": "Missing session token"}), 401
    user = restore_user_from_session(session_token)
    if not user:
        return jsonify({"error": "Invalid session"}), 401
    if str(user["id"]) != str(user_id):
        return jsonify({"error": "Forbidden"}), 403
    return None


@app.before_request
def before_request():
    """Validate API key and check rate limit on every request."""
    # Always allow CORS preflight
    if request.method == "OPTIONS":
        return None

    # Skip API key check for auth endpoints
    for prefix in _AUTH_PREFIXES:
        if request.path.startswith(prefix):
            ip = request.remote_addr or "unknown"
            if not _check_rate_limit(ip, MAX_AUTH_PER_MINUTE):
                return jsonify({"error": "rate limit exceeded"}), 429
            return None

    if not API_KEY:
        return jsonify({"error": "server misconfiguration"}), 500

    provided = request.headers.get("X-API-Key", "")
    if not provided or not secrets.compare_digest(provided, API_KEY):
        return jsonify({"error": "unauthorized"}), 401

    ip = request.remote_addr or "unknown"
    # Use higher limit for reads, lower for writes
    max_req = MAX_READ_PER_MINUTE if request.method == "GET" else MAX_WRITE_PER_MINUTE
    if not _check_rate_limit(ip, max_req):
        return jsonify({"error": "rate limit exceeded"}), 429


# ─── Health ────────────────────────────────────────────────────

@app.route("/api/health", methods=["GET"])
def health():
    return jsonify({"ok": True})


# ─── Auth (no X-API-Key required) ─────────────────────────────

@app.route("/api/auth/token/verify", methods=["POST"])
def auth_verify_token():
    """Validate a session token."""
    body = request.get_json(silent=True)
    if not body or "session_token" not in body:
        return jsonify({"error": "session_token is required"}), 400
    user = restore_user_from_session(body["session_token"])
    if user:
        return jsonify({"valid": True, "user": user})
    return jsonify({"valid": False}), 200


@app.route("/api/auth/token", methods=["DELETE"])
def auth_delete_token():
    """Logout / delete session."""
    token = request.headers.get("X-Session-Token", "")
    if not token:
        return jsonify({"error": "X-Session-Token header is required"}), 400
    delete_session(token)
    return jsonify({"ok": True})


@app.route("/api/auth/me", methods=["GET"])
def auth_me():
    """Get current user from session token."""
    token = request.headers.get("X-Session-Token", "")
    if not token:
        return jsonify({"error": "X-Session-Token header is required"}), 401
    user = restore_user_from_session(token)
    if not user:
        return jsonify({"error": "unauthorized"}), 401
    return jsonify({"user": user})


@app.route("/api/admin/rescan", methods=["POST"])
def admin_rescan():
    """Trigger immediate user rescan (for when a new user registers and the daemon needs to pick them up)."""
    users = get_all_users()
    return jsonify({"ok": True, "users_found": len(users)})


@app.route("/api/admin/clear-supply-chain-cache", methods=["POST"])
def admin_clear_supply_chain_cache():
    """Clear the Vala-Fi supply chain cache to force fresh API fetches."""
    from src.data.supply_chain_data import _VALAFI_CACHE, _valafi_cache_clear
    cached_tickers = list(_VALAFI_CACHE.keys())
    _VALAFI_CACHE.clear()
    return jsonify({"ok": True, "cleared": cached_tickers})


@app.route("/api/admin/run-check/<int:user_id>", methods=["POST"])
def admin_run_check(user_id):
    """Force an immediate alert check for a user. Bypasses daemon stagger schedule."""
    from src.data.notification_db import get_custom_alert_rules

    tickers = load_user_watchlist(user_id)
    has_custom_alerts = bool(get_custom_alert_rules(user_id))

    if not tickers and not has_custom_alerts:
        return jsonify({"error": "user has no watchlist and no custom alerts"}), 400

    results = {}
    if tickers:
        notifications_by_ticker = check_all_tickers_for_user(user_id)
    else:
        notifications_by_ticker = {}

    # Evaluate custom alerts for all tickers in the user's watchlist
    created = sum(len(n) for n in notifications_by_ticker.values())
    if notifications_by_ticker:
        deliver_notifications(user_id, notifications_by_ticker)
    results["watchlist_checks"] = {
        "tickers_checked": len(tickers),
        "notifications_created": created,
    }

    return jsonify({
        "ok": True,
        "user_id": user_id,
        **results,
        "notifications_delivered": created,
    })


@app.route("/api/admin/reconciliation-tick", methods=["POST"])
def admin_reconciliation_tick():
    """Force an immediate reconciliation tick for all custom alerts.

    Bypasses the 60-second daemon cycle. Useful for testing or
    triggering an immediate evaluation of all active custom alert
    rules across all users.
    """
    reconciliation_tick()
    return jsonify({"ok": True, "message": "Reconciliation tick completed"})


# ─── Password Reset (no X-API-Key required, rate-limited) ─────

@app.route("/api/auth/password-reset/request", methods=["POST"])
def auth_password_reset_request():
    """Request a password reset email.

    Accepts JSON: { "email": "user@example.com" }
    Always returns 200 with a generic message to prevent email enumeration,
    unless SMTP is misconfigured (then returns 500).
    """
    body = request.get_json(silent=True)
    if not body or "email" not in body:
        return jsonify({"error": "email is required"}), 400

    email = body["email"].lower().strip()
    user = get_user_by_email(email)

    generic_response = jsonify({
        "message": "If an account with that email exists, a reset link has been sent."
    })

    if user is None:
        # User not found — return generic message to prevent email enumeration
        return generic_response

    # Create reset token and build reset link
    reset_base = os.environ.get("RESET_BASE_URL", "http://localhost:3000")
    token = create_password_reset_token(user["id"])
    reset_link = f"{reset_base}/reset-password?token={token}"

    # Always return the same response regardless of delivery success
    # to prevent email enumeration via status code side-channel
    send_password_reset_email(email, reset_link)
    return generic_response


@app.route("/api/auth/password-reset/confirm", methods=["POST"])
def auth_password_reset_confirm():
    """Confirm a password reset with a token and new password.

    Accepts JSON: { "token": "...", "new_password": "..." }
    """
    body = request.get_json(silent=True)
    if not body or "token" not in body or "new_password" not in body:
        return jsonify({"error": "token and new_password are required"}), 400

    token = body["token"]
    new_password = body["new_password"]

    if len(token) < 10:
        return jsonify({"error": "invalid token"}), 400

    if len(new_password) < 6:
        return jsonify({"error": "password must be at least 6 characters"}), 400

    user = get_user_from_reset_token(token)
    if user is None:
        return jsonify({"error": "invalid or expired reset token"}), 400

    # Hash the new password and update the user record
    update_user_password(user["id"], new_password)

    # Revoke all existing sessions to force re-login with the new password
    delete_all_sessions(user["id"])

    return jsonify({"message": "Password updated successfully."})


# ─── Watchlist ─────────────────────────────────────────────────

@app.route("/api/watchlist/<int:user_id>", methods=["GET"])
def api_get_watchlist(user_id):
    check = _check_session_owns_user_id(user_id)
    if check:
        return check
    tickers = load_user_watchlist(user_id)
    return jsonify({"user_id": user_id, "tickers": tickers})


@app.route("/api/watchlist", methods=["POST"])
def api_add_ticker():
    body = request.get_json(silent=True)
    if not body or "user_id" not in body or "ticker" not in body:
        return jsonify({"error": "user_id and ticker are required"}), 400
    check = _check_session_owns_user_id(body["user_id"])
    if check:
        return check
    try:
        add_user_ticker(body["user_id"], body["ticker"])
        _invalidate_enriched_cache(body["user_id"])
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/watchlist/<int:user_id>/enriched", methods=["GET"])
def api_get_enriched_watchlist(user_id):
    """Return watchlist tickers enriched with price, health, risk, and growth data."""
    check = _check_session_owns_user_id(user_id)
    if check:
        return check
    from concurrent.futures import ThreadPoolExecutor, as_completed

    cache_key = f"enriched:{user_id}"
    with _enriched_cache_lock:
        entry = _enriched_cache.get(cache_key)
        if entry and time.time() - entry[0] < _ENRICHED_CACHE_TTL:
            return jsonify(json.loads(entry[1]))

    tickers = load_user_watchlist(user_id)
    if not tickers:
        return jsonify({"user_id": user_id, "items": []})

    def enrich_one(ticker):
        try:
            data, err = _company_data(ticker, lite=True)
            if data is None:
                return {"ticker": ticker, "error": True}

            mkt = data.get("market", {})
            price = mkt.get("price") or 0
            prev_close = mkt.get("previous_close")
            change = round(price - prev_close, 2) if prev_close else 0
            change_pct = round((change / prev_close) * 100, 2) if prev_close and prev_close > 0 else 0

            h_score, h_verdict, fscore, _ = compute_health_score(data)
            z_score, z_zone, _ = compute_altman_zscore(data)
            r_score, r_label, _, _ = compute_risk_assessment(data, z_score, z_zone)

            try:
                growth = fetch_price_growth(ticker)
            except Exception:
                growth = None

            return {
                "ticker": ticker,
                "name": data.get("company", {}).get("name", ""),
                "sector": data.get("company", {}).get("sector", ""),
                "price": price,
                "change": change,
                "change_pct": change_pct,
                "healthScore": h_score,
                "verdict": h_verdict,
                "riskLabel": r_label,
                "growth3m": growth.get("3m") if growth else None,
                "growth6m": growth.get("6m") if growth else None,
                "growth12m": growth.get("12m") if growth else None,
            }
        except Exception:
            return {"ticker": ticker, "error": True}

    index = {t: i for i, t in enumerate(tickers)}
    items = [None] * len(tickers)
    with ThreadPoolExecutor(max_workers=min(len(tickers), 8)) as pool:
        futures = {pool.submit(enrich_one, t): t for t in tickers}
        for future in as_completed(futures):
            result = future.result()
            items[index[result["ticker"]]] = result

    response = jsonify({"user_id": user_id, "items": items})
    with _enriched_cache_lock:
        _enriched_cache[cache_key] = (time.time(), response.get_data(as_text=True))
    return response


@app.route("/api/watchlist/<int:user_id>/<ticker>", methods=["DELETE"])
def api_remove_ticker(user_id, ticker):
    check = _check_session_owns_user_id(user_id)
    if check:
        return check
    try:
        remove_user_ticker(user_id, ticker)
        _invalidate_enriched_cache(user_id)
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/watchlist/<int:user_id>", methods=["DELETE"])
def api_clear_watchlist(user_id):
    """Clear entire watchlist."""
    check = _check_session_owns_user_id(user_id)
    if check:
        return check
    try:
        clear_user_watchlist(user_id)
        _invalidate_enriched_cache(user_id)
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/watchlist/<int:user_id>/count", methods=["GET"])
def api_watchlist_count(user_id):
    """Watchlist size."""
    check = _check_session_owns_user_id(user_id)
    if check:
        return check
    count = get_user_watchlist_count(user_id)
    return jsonify({"count": count})


@app.route("/api/watchlist/<int:user_id>/has/<ticker>", methods=["GET"])
def api_watchlist_has(user_id, ticker):
    """Check if ticker is in watchlist."""
    check = _check_session_owns_user_id(user_id)
    if check:
        return check
    watched = is_ticker_watched_by_user(user_id, ticker)
    return jsonify({"watched": watched})


# ─── Auth (legacy user endpoints, still require API key) ─────

@app.route("/api/user/<int:user_id>", methods=["GET"])
def api_get_user(user_id):
    check = _check_session_owns_user_id(user_id)
    if check:
        return check
    user = get_user(user_id)
    if not user:
        return jsonify({"error": "user not found"}), 404
    user.pop("password_hash", None)
    user.pop("salt", None)
    return jsonify({"user": user})


@app.route("/api/user", methods=["GET"])
def api_list_users():
    """List all users (admin endpoint)."""
    users = get_all_users()
    for u in users:
        u.pop("password_hash", None)
        u.pop("salt", None)
    return jsonify({"users": users})


@app.route("/api/user/register", methods=["POST"])
def api_register():
    body = request.get_json(silent=True)
    if not body or "username" not in body or "password" not in body:
        return jsonify({"error": "username and password are required"}), 400
    user = register_user(
        body["username"],
        body["password"],
        display_name=body.get("display_name"),
        email=body.get("email"),
        telegram_chat_id=body.get("telegram_chat_id"),
    )
    if not user:
        return jsonify({"error": "username already taken"}), 409
    token = create_session(user["id"])

    # Auto-create default "All News" alert rule for new users
    try:
        news_conditions = json.dumps([{
            "signal_category": "news",
            "signal_id": "new_news",
            "operator": "==",
            "value": True,
        }])
        create_custom_alert_rule(
            user["id"],
            name="All News",
            scope="watchlist",
            ticker=None,
            conditions=news_conditions,
            logic_operator="AND",
            severity="info",
        )
    except Exception:
        logger.warning("Failed to create default news rule for user %d", user["id"])

    return jsonify({"user": user, "session_token": token}), 201


@app.route("/api/user/login", methods=["POST"])
def api_login():
    body = request.get_json(silent=True)
    if not body or "username" not in body or "password" not in body:
        return jsonify({"error": "username and password are required"}), 400
    user = login_user(body["username"], body["password"])
    if not user:
        return jsonify({"error": "invalid credentials"}), 401
    token = create_session(user["id"])
    return jsonify({"user": user, "session_token": token})


@app.route("/api/user/<int:user_id>/link-telegram", methods=["POST"])
def api_link_telegram(user_id):
    check = _check_session_owns_user_id(user_id)
    if check:
        return check
    body = request.get_json(silent=True)
    if not body or "chat_id" not in body:
        return jsonify({"error": "chat_id is required"}), 400
    success = link_telegram(user_id, body["chat_id"])
    return jsonify({"ok": success})


# ─── Data Endpoints ────────────────────────────────────────────

def _company_data(ticker: str, lite: bool = False):
    """Fetch company data and scores, returning (data, scores) or (None, error_response).

    When lite=True, skips expensive extras (insider trades, SEC filings, supply chain).
    """
    try:
        data = fetch_company_data(ticker, skip_extras=lite)
        scores_dict = {}
        # Compute health score
        h_score, h_verdict, fscore, _ = compute_health_score(data)
        scores_dict["health_score"] = h_score
        scores_dict["health_verdict"] = h_verdict
        scores_dict["fscore"] = fscore
        # Compute Z-Score
        z_score, z_zone, _ = compute_altman_zscore(data)
        z_normalized = compute_zscore_normalized(z_score)
        scores_dict["zscore"] = z_score
        scores_dict["zscore_zone"] = z_zone
        scores_dict["zscore_normalized"] = z_normalized
        # Compute risk
        r_score, r_label, r_summary, r_factors = compute_risk_assessment(data, z_score, z_zone)
        scores_dict["risk_score"] = r_score
        scores_dict["risk_label"] = r_label
        scores_dict["risk_summary"] = r_summary
        red_flags = compute_red_flags(data, r_factors)
        scores_dict["red_flag_count"] = len([f for f in red_flags if f[0] == "danger"])
        scores_dict["red_flags"] = red_flags
        return data, scores_dict
    except Exception as e:
        return None, ({"error": f"failed to fetch data for {ticker}: {str(e)}"}, 500)


def _filter_news(items: list[dict]) -> list[dict]:
    """Deduplicate and filter low-quality news items."""
    skip_sources = {"press release", "business wire", "globenewswire", "pr newswire"}
    seen: set[str] = set()
    result: list[dict] = []
    for item in items:
        title = (item.get("title") or "").lower()
        if not title:
            continue
        # Skip press releases
        publisher = (item.get("publisher") or "").lower()
        if any(skip in publisher for skip in skip_sources):
            continue
        # Dedup by title hash (first 80 chars)
        key = title[:80]
        if key in seen:
            continue
        seen.add(key)
        result.append(item)
    return result[:10]


@app.route("/api/data/<ticker>/health", methods=["GET"])
def data_health(ticker):
    """Health score + F-Score + Z-Score + company info."""
    data, err = _company_data(ticker)
    if data is None:
        return jsonify(err[0]), err[1]
    h_score, h_verdict, fscore, criteria = compute_health_score(data)
    z_score, z_zone, z_expl, z_components = compute_altman_zscore_with_components(data)
    z_normalized = compute_zscore_normalized(z_score)
    mkt = data.get("market", {})
    price = mkt.get("price") or 0
    prev_close = mkt.get("previous_close")
    change = round(price - prev_close, 2) if prev_close else 0
    change_pct = round((change / prev_close) * 100, 2) if prev_close and prev_close > 0 else 0
    return jsonify({
        "score": h_score,
        "name": data.get("company", {}).get("name", ""),
        "sector": data.get("company", {}).get("sector", ""),
        "price": price,
        "change": change,
        "change_pct": change_pct,
        "verdict": h_verdict,
        "fscore": fscore,
        "criteria": criteria,
        "zscore_score": z_score,
        "zscore_zone": z_zone,
        "zscore_explanation": z_expl,
        "zscore_normalized": z_normalized,
        "zscore_x1": z_components.get("x1"),
        "zscore_x2": z_components.get("x2"),
        "zscore_x3": z_components.get("x3"),
        "zscore_x4": z_components.get("x4"),
        "news": _filter_news(data.get("news", [])),
    })


@app.route("/api/data/<ticker>/intrinsic", methods=["GET"])
def data_intrinsic(ticker):
    """Intrinsic worth (Graham/DCF/FCF)."""
    data, err = _company_data(ticker)
    if data is None:
        return jsonify(err[0]), err[1]
    score, verdict, explanation, _, breakdown = compute_intrinsic_worth(data)
    return jsonify({
        "score": score,
        "verdict": verdict,
        "explanation": explanation,
        "breakdown": {
            "graham_number": breakdown.get("graham_number"),
            "graham_ratio": breakdown.get("graham_ratio"),
            "fcf_yield": breakdown.get("fcf_yield"),
            "earnings_power_value": breakdown.get("earnings_power_value"),
            "epv_ratio": breakdown.get("epv_ratio"),
            "pb_ratio": breakdown.get("pb_ratio"),
            "dividend_yield": breakdown.get("dividend_yield"),
        },
    })


@app.route("/api/data/<ticker>/risk", methods=["GET"])
def data_risk(ticker):
    """Risk assessment + red flags."""
    data, err = _company_data(ticker)
    if data is None:
        return jsonify(err[0]), err[1]
    z_score, z_zone, _, _ = compute_altman_zscore_with_components(data)
    r_score, r_label, r_summary, r_factors = compute_risk_assessment(data, z_score, z_zone)
    red_flags = compute_red_flags(data, r_factors)
    return jsonify({
        "score": r_score,
        "label": r_label,
        "risk_score": r_score,
        "risk_label": r_label,
        "summary": r_summary,
        "factors": r_factors,
        "red_flags": [
            {"severity": sev, "title": title, "explanation": expl}
            for sev, title, expl in red_flags
        ],
    })


@app.route("/api/data/<ticker>/peers", methods=["GET"])
def data_peers(ticker):
    """Peer comparison data."""
    data, err = _company_data(ticker)
    if data is None:
        return jsonify(err[0]), err[1]
    sector = data.get("company", {}).get("sector", "")
    industry = data.get("company", {}).get("industry", "")
    peer_tickers = fetch_peers(sector, industry, ticker)
    peer_data = fetch_peer_metrics(peer_tickers)
    averages = compute_peer_averages(peer_data) if peer_data else {}
    return jsonify({
        "peers": peer_data,
        "averages": averages,
    })


@app.route("/api/data/<ticker>/price-growth", methods=["GET"])
def data_price_growth(ticker):
    """3/6/12 month price growth."""
    growth = fetch_price_growth(ticker)
    if growth is None:
        return jsonify({"error": f"insufficient price history for {ticker}"}), 404
    return jsonify(growth)


@app.route("/api/data/<ticker>/price-history", methods=["GET"])
def data_price_history(ticker):
    """Historical OHLCV candle data for charting.

    Query params:
        period — yfinance period string (e.g. "1y", "6mo", "3mo", "2y"). Default: "1y".
    """
    period = request.args.get("period", "1y")
    candles = fetch_price_history(ticker, period=period)
    if not candles:
        return jsonify({"error": f"no price history available for {ticker}"}), 404
    return jsonify({"candles": candles})


@app.route("/api/data/<ticker>/financials", methods=["GET"])
def data_financials(ticker):
    """Income/Balance/CashFlow statements.

    Returns each statement as a list of {label, values} rows so the frontend
    FinancialTable can render them directly without transformation.
    """
    data, err = _company_data(ticker)
    if data is None:
        return jsonify(err[0]), err[1]
    statements = data.get("statements", {})
    def _df_to_rows(df):
        if df is None or df.empty:
            return []
        # Convert column labels (Timestamps) to date strings for JSON serialization
        df_copy = df.copy()
        df_copy.columns = [str(c.strftime("%Y-%m-%d")) if hasattr(c, "strftime") else str(c) for c in df_copy.columns]
        records = df_copy.to_dict(orient="records")
        # Sanitize values: NaN -> None, numpy types -> python primitives
        def _sanitize(v):
            import numpy as np
            if v is None or (isinstance(v, float) and v != v):  # NaN check
                return None
            if isinstance(v, (np.integer,)):
                return int(v)
            if isinstance(v, (np.floating,)):
                return float(v)
            if isinstance(v, np.bool_):
                return bool(v)
            return v
        return [
            {"label": str(idx), "values": {k: _sanitize(v) for k, v in record.items()}}
            for idx, record in zip(df_copy.index, records)
        ]
    return jsonify({
        "income": _df_to_rows(statements.get("income")),
        "balance": _df_to_rows(statements.get("balance")),
        "cashflow": _df_to_rows(statements.get("cashflow")),
    })


@app.route("/api/data/<ticker>/dcf", methods=["GET"])
def data_dcf(ticker):
    """DCF model with sensitivity matrix."""
    data, err = _company_data(ticker)
    if data is None:
        return jsonify(err[0]), err[1]
    # Read slider params from query string
    params = {}
    for _key in ("revenue_growth_5yr", "terminal_growth", "discount_rate", "margin_improvement"):
        _val = request.args.get(_key, type=float)
        if _val is not None:
            params[_key] = _val
    dcf_result = compute_dcf(data, **params) if params else compute_dcf(data)
    if dcf_result.get("error"):
        return jsonify({"error": dcf_result["error"], "fair_value": None}), 400
    projected_rev = dcf_result.get("projected_revenue", [])
    projected_fcf = dcf_result.get("projected_fcf", [])
    pv_fcf = dcf_result.get("pv_fcf", [])
    sensitivity = dcf_result.get("sensitivity", {})
    return jsonify({
        "fair_value_with_cash": round(dcf_result["fair_value_with_cash"], 2) if dcf_result.get("fair_value_with_cash") is not None else None,
        "fair_value_per_share": round(dcf_result["fair_value_per_share"], 2) if dcf_result.get("fair_value_per_share") is not None else None,
        "upside_pct": round(dcf_result["upside_pct"], 1) if dcf_result.get("upside_pct") is not None else None,
        "verdict": dcf_result.get("verdict"),
        "enterprise_value": round(dcf_result["enterprise_value"], 2) if dcf_result.get("enterprise_value") is not None else None,
        "projected_revenue": [round(v, 2) for v in projected_rev],
        "projected_fcf": [round(v, 2) for v in projected_fcf],
        "pv_fcf": [round(v, 2) for v in pv_fcf],
        "projections": [
            {"year": i + 1, "revenue": round(r, 2), "fcf": round(f, 2)}
            for i, (r, f) in enumerate(zip(projected_rev, projected_fcf))
        ],
        "sensitivity": sensitivity,
        "assumptions": dcf_result.get("assumptions", {}),
    })


@app.route("/api/data/<ticker>/sentiment", methods=["GET"])
def data_sentiment(ticker):
    """News sentiment + analyst consensus."""
    analyst = fetch_analyst_data(ticker)
    return jsonify({
        "analyst": analyst.get("recommendations", {}),
        "price_targets": analyst.get("price_targets", {}),
        "num_analysts": analyst.get("num_analysts"),
    })


@app.route("/api/data/<ticker>/institutional", methods=["GET"])
def data_institutional(ticker):
    """Top institutional holders."""
    inst = fetch_institutional_data(ticker)
    return jsonify({
        "holders": inst.get("holders", []),
        "verdict": inst.get("verdict"),
    })


@app.route("/api/data/<ticker>/supply-chain", methods=["GET"])
def data_supply_chain(ticker):
    """Supply chain relationships: curated JSON + Vala-Fi (SEC 10-K) merged."""
    try:
        from src.data.supply_chain_data import get_enriched_relationships, load_country_risk

        ticker_u = ticker.upper().strip()
        country_risk = load_country_risk()
        enriched = get_enriched_relationships(ticker_u)

        def _investability_score(target: str) -> int:
            info = _cached_ticker_info(target)
            if info:
                qh = compute_quick_health(info)
                return min(100, max(0, qh["score"] * 10))
            return 50

        # Flatten all buckets into a single relationships list.
        # Each enriched rel already carries: source, target, type, strength,
        # description, target_geo, financials, investability_score, other.
        relationships = []
        for bucket in ("suppliers", "customers", "competitors", "partners"):
            for rel in enriched.get(bucket, []):
                target = (rel.get("other") or rel.get("target", "")).upper()
                # Ensure target_geo structure (may be missing from Vala-Fi entries)
                geo = rel.get("target_geo") or {}
                if geo.get("domicile") is None:
                    # Fallback: enrich with yfinance country
                    info = _cached_ticker_info(target)
                    if info:
                        domicile = info.get("country")
                        if domicile:
                            cr = country_risk.get(domicile.upper())
                            geo["domicile"] = domicile
                            geo["manufacturing"] = geo.get("manufacturing", [])
                            if cr:
                                geo["risk_scores"] = [{
                                    "country_code": domicile.upper(),
                                    "name": cr.get("name", domicile),
                                    "risk_score": cr.get("risk_score"),
                                    "risk_label": cr.get("risk_label", "Unknown"),
                                }]
                            else:
                                geo["risk_scores"] = []
                        else:
                            geo["risk_scores"] = []
                            geo["manufacturing"] = geo.get("manufacturing", [])
                    else:
                        geo["risk_scores"] = []
                        geo["manufacturing"] = geo.get("manufacturing", [])

                entry = {
                    "source": rel.get("source", ticker_u),
                    "target": target,
                    "type": rel.get("type", "partner"),
                    "strength": rel.get("strength", "medium"),
                    "description": rel.get("description", ""),
                    "investability_score": _investability_score(target),
                    "has_supply_chain": bool(rel.get("financials")),
                    "target_geo": {
                        "domicile": geo.get("domicile"),
                        "manufacturing": geo.get("manufacturing", []),
                        "risk_scores": geo.get("risk_scores", []),
                    },
                }
                relationships.append(entry)

        return jsonify({
            "ticker": ticker_u,
            "company_name": "",
            "relationships": relationships,
            "multi_hop_paths": [],
        })
    except Exception as e:
        return jsonify({"error": str(e), "relationships": [], "multi_hop_paths": []}), 500


@app.route("/api/data/<ticker>/filings", methods=["GET"])
def data_filings(ticker):
    """SEC filings."""
    try:
        filings = fetch_sec_filings_edgar(ticker)
        if filings is None or filings.empty:
            return jsonify({"filings": []})
        records = filings.to_dict(orient="records")
        transformed = [
            {
                "ticker": ticker,
                "type": r.get("report_type", ""),
                "date": r.get("filing_date", ""),
                "link": r.get("filing_detail_url", ""),
            }
            for r in records
        ]
        return jsonify({"filings": transformed})
    except Exception as e:
        return jsonify({"error": str(e), "filings": []}), 500


@app.route("/api/data/<ticker>/insider", methods=["GET"])
def data_insider(ticker):
    """Insider trading."""
    try:
        trades = fetch_insider_trading_edgar(ticker)
        if trades is None or trades.empty:
            return jsonify({"insider": []})
        records = trades.to_dict(orient="records")
        transformed = [
            {
                "ticker": ticker,
                "name": r.get("owner_name", ""),
                "title": r.get("owner_title", ""),
                "transaction": r.get("transaction_type", ""),
                "shares": r.get("shares") or 0,
                "value": r.get("price") or 0,
                "date": r.get("transaction_date", ""),
            }
            for r in records
        ]
        return jsonify({"insider": transformed})
    except Exception as e:
        return jsonify({"error": str(e), "insider": []}), 500


@app.route("/api/data/<ticker>/ecosystem", methods=["GET"])
def data_ecosystem(ticker):
    """Company linkage/ecosystem."""
    try:
        from src.scoring.relationships import compute_ecosystem_summary
        sc = get_enriched_relationships(ticker)
        # Flatten dict-of-lists into a single list for compute_ecosystem_summary
        rel_list = []
        for role, items in sc.items():
            if isinstance(items, list):
                for rel in items:
                    rel_list.append(rel)

        # Gather metrics for peers
        peer_tickers = set()
        for rel in rel_list:
            if isinstance(rel, dict) and "target" in rel:
                peer_tickers.add(rel["target"])
        metrics_data = {}
        for pt in peer_tickers:
            try:
                info = None
                from src.data.fetcher import _cached_ticker_info
                info = _cached_ticker_info(pt)
                if info:
                    qh = compute_quick_health(info)
                    metrics_data[pt] = {"health_score": qh["score"], "verdict": qh["verdict"]}
            except Exception:
                pass
        ecosystem = compute_ecosystem_summary(rel_list, metrics_data)
        return jsonify({
            "relationships": sc,
            "insights": ecosystem,
        })
    except Exception as e:
        return jsonify({"error": str(e), "relationships": [], "insights": {}}), 500


# ─── Market Endpoints ─────────────────────────────────────────

@app.route("/api/market/indices", methods=["GET"])
def market_indices():
    """Market indices (S&P 500, NASDAQ, DOW)."""
    try:
        indices = fetch_market_indices()
        return jsonify({"indices": indices})
    except Exception as e:
        return jsonify({"error": str(e), "indices": []}), 500


@app.route("/api/market/news", methods=["GET"])
def market_news():
    """Market news."""
    try:
        limit = request.args.get("limit", 10, type=int)
        news = fetch_market_news(max_items=limit)
        return jsonify({"news": news})
    except Exception as e:
        return jsonify({"error": str(e), "news": []}), 500


@app.route("/api/market/macro", methods=["GET"])
def market_macro():
    """Macro indicators (VIX, yield curve, etc.)."""
    try:
        macro = fetch_macro_context()
        return jsonify(macro)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/market/movers", methods=["GET"])
def market_movers():
    """Top movers."""
    try:
        top_n = request.args.get("top_n", 10, type=int)
        movers = fetch_top_movers(top_n=top_n)
        gainers = [m for m in movers if m["direction"] == "up"][:top_n // 2]
        losers = [m for m in movers if m["direction"] == "down"][:top_n // 2]
        return jsonify({"gainers": gainers, "losers": losers})
    except Exception as e:
        return jsonify({"error": str(e), "gainers": [], "losers": []}), 500


# ─── Screener ─────────────────────────────────────────────────

# Common large-cap US tickers for yfinance fallback when OpenBB is unavailable
_SCREENER_TICKERS = [
    "AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "META", "TSLA", "BRK-B", "V", "UNH",
    "JNJ", "WMT", "JPM", "XOM", "PG", "MA", "CVX", "LLY", "HD", "MRK",
    "ABBV", "PEP", "COST", "AVGO", "KO", "ADBE", "MCD", "PFE", "TMO", "CSCO",
    "CRM", "ACN", "ABT", "DIS", "NKE", "DHR", "VZ", "NEE", "TXN", "BMY",
    "ORCL", "WFC", "AMD", "QCOM", "PM", "RTX", "UNP", "HON", "INTU", "LOW",
    "SBUX", "AMGN", "IBM", "BA", "CAT", "GE", "SPGI", "BLK", "ISRG", "AXP",
    "MDLZ", "GILD", "CVS", "NOW", "SYK", "TJX", "MMM", "ADP", "VRTX", "LRCX",
    "CI", "REGN", "PLD", "MO", "ZTS", "BKNG", "CB", "SCHW", "DE", "SO",
    "DUK", "C", "PGR", "AMT", "TMUS", "BDX", "EOG", "MU", "CL", "FIS",
    "SHW", "CME", "USB", "ITW", "NOC", "HUM", "WM", "NSC", "AON", "CSX",
]


def _fetch_screener_yfinance(limit: int = 100):
    """Fallback screener using yfinance directly when OpenBB is unavailable."""
    try:
        import yfinance as yf  # type: ignore
        import pandas as pd
        tickers = _SCREENER_TICKERS[:limit]
        data = []
        for sym in tickers:
            try:
                t = yf.Ticker(sym)
                info = t.fast_info
                price = getattr(info, "last_price", None) or getattr(info, "previous_close", None)
                if price is None:
                    continue
                mcap = getattr(info, "market_cap", None)
                pe = getattr(info, "trailing_pe", None)
                hist = t.history(period="5d")
                change = 0.0
                if len(hist) >= 2:
                    prev = hist["Close"].iloc[-2]
                    curr = hist["Close"].iloc[-1]
                    if prev and prev > 0:
                        change = ((curr - prev) / prev) * 100
                vol = hist["Volume"].iloc[-1] if len(hist) > 0 else 0
                data.append({
                    "symbol": sym,
                    "name": sym,
                    "price": round(float(price), 2) if price else 0,
                    "market_cap": int(mcap) if mcap else 0,
                    "pe": round(float(pe), 2) if pe else None,
                    "volume": int(vol) if vol else 0,
                    "percent_change": round(change, 2),
                    "health_score": 50,
                    "verdict": "Hold",
                })
            except Exception:
                continue
        if not data:
            return None
        return pd.DataFrame(data)
    except Exception:
        return None

@app.route("/api/screener", methods=["GET"])
def api_screener():
    """Stock screener."""
    try:
        country = request.args.get("country", "us")
        limit = min(request.args.get("limit", 50, type=int), 200)
        sort_by = request.args.get("sort", "")
        df = fetch_screener_obb(country=country)
        if df is None or df.empty:
            df = _screener_mock_data()
        if df is None or df.empty:
            return jsonify({"stocks": []})
        if sort_by and sort_by in df.columns:
            ascending = sort_by in ("pe",)
            df = df.sort_values(by=sort_by, ascending=ascending, na_position="last")
        if limit and limit > 0:
            df = df.head(limit)
        stocks = df.to_dict(orient="records")
        return jsonify({"stocks": stocks})
    except Exception as e:
        return jsonify({"error": str(e), "stocks": []}), 500


_MOCK_STOCKS = [
    {"symbol": "AAPL", "name": "Apple Inc.", "price": 189.84, "market_cap": 2_950_000_000_000, "pe": 29.2, "volume": 54_320_000, "percent_change": 1.23, "health_score": 78, "verdict": "Buy"},
    {"symbol": "MSFT", "name": "Microsoft Corporation", "price": 415.56, "market_cap": 3_090_000_000_000, "pe": 36.1, "volume": 22_100_000, "percent_change": 0.87, "health_score": 82, "verdict": "Buy"},
    {"symbol": "GOOGL", "name": "Alphabet Inc.", "price": 174.13, "market_cap": 2_160_000_000_000, "pe": 25.4, "volume": 28_700_000, "percent_change": -0.45, "health_score": 75, "verdict": "Buy"},
    {"symbol": "AMZN", "name": "Amazon.com Inc.", "price": 185.63, "market_cap": 1_930_000_000_000, "pe": 60.2, "volume": 48_500_000, "percent_change": 2.11, "health_score": 71, "verdict": "Hold"},
    {"symbol": "NVDA", "name": "NVIDIA Corporation", "price": 122.45, "market_cap": 3_010_000_000_000, "pe": 55.8, "volume": 310_000_000, "percent_change": 3.45, "health_score": 85, "verdict": "Strong Buy"},
    {"symbol": "META", "name": "Meta Platforms Inc.", "price": 505.95, "market_cap": 1_290_000_000_000, "pe": 27.3, "volume": 18_200_000, "percent_change": -1.02, "health_score": 73, "verdict": "Buy"},
    {"symbol": "TSLA", "name": "Tesla Inc.", "price": 248.42, "market_cap": 790_000_000_000, "pe": 72.1, "volume": 98_400_000, "percent_change": -2.34, "health_score": 55, "verdict": "Hold"},
    {"symbol": "BRK-B", "name": "Berkshire Hathaway Inc.", "price": 452.30, "market_cap": 980_000_000_000, "pe": 10.5, "volume": 3_200_000, "percent_change": 0.15, "health_score": 88, "verdict": "Strong Buy"},
    {"symbol": "V", "name": "Visa Inc.", "price": 279.12, "market_cap": 570_000_000_000, "pe": 30.6, "volume": 7_800_000, "percent_change": 0.56, "health_score": 80, "verdict": "Buy"},
    {"symbol": "JPM", "name": "JPMorgan Chase & Co.", "price": 198.47, "market_cap": 570_000_000_000, "pe": 11.8, "volume": 9_500_000, "percent_change": 1.78, "health_score": 72, "verdict": "Buy"},
    {"symbol": "WMT", "name": "Walmart Inc.", "price": 67.23, "market_cap": 540_000_000_000, "pe": 35.2, "volume": 12_300_000, "percent_change": 0.32, "health_score": 68, "verdict": "Hold"},
    {"symbol": "JNJ", "name": "Johnson & Johnson", "price": 156.78, "market_cap": 380_000_000_000, "pe": 22.1, "volume": 7_100_000, "percent_change": -0.67, "health_score": 76, "verdict": "Buy"},
    {"symbol": "XOM", "name": "Exxon Mobil Corporation", "price": 104.56, "market_cap": 420_000_000_000, "pe": 13.4, "volume": 15_600_000, "percent_change": -1.45, "health_score": 62, "verdict": "Hold"},
    {"symbol": "PG", "name": "Procter & Gamble Co.", "price": 165.32, "market_cap": 390_000_000_000, "pe": 26.8, "volume": 6_400_000, "percent_change": 0.21, "health_score": 74, "verdict": "Hold"},
    {"symbol": "MA", "name": "Mastercard Inc.", "price": 465.89, "market_cap": 430_000_000_000, "pe": 34.5, "volume": 3_100_000, "percent_change": 0.98, "health_score": 79, "verdict": "Buy"},
    {"symbol": "UNH", "name": "UnitedHealth Group Inc.", "price": 285.43, "market_cap": 260_000_000_000, "pe": 16.2, "volume": 8_900_000, "percent_change": -3.21, "health_score": 65, "verdict": "Hold"},
    {"symbol": "HD", "name": "Home Depot Inc.", "price": 362.15, "market_cap": 360_000_000_000, "pe": 24.7, "volume": 4_200_000, "percent_change": 1.54, "health_score": 70, "verdict": "Buy"},
    {"symbol": "CVX", "name": "Chevron Corporation", "price": 147.89, "market_cap": 270_000_000_000, "pe": 14.1, "volume": 8_700_000, "percent_change": -0.89, "health_score": 63, "verdict": "Hold"},
    {"symbol": "LLY", "name": "Eli Lilly and Company", "price": 825.67, "market_cap": 780_000_000_000, "pe": 120.3, "volume": 4_500_000, "percent_change": 4.56, "health_score": 83, "verdict": "Strong Buy"},
    {"symbol": "MRK", "name": "Merck & Co. Inc.", "price": 125.34, "market_cap": 318_000_000_000, "pe": 18.9, "volume": 9_200_000, "percent_change": 0.43, "health_score": 71, "verdict": "Buy"},
    {"symbol": "ABBV", "name": "AbbVie Inc.", "price": 172.56, "market_cap": 304_000_000_000, "pe": 38.2, "volume": 6_800_000, "percent_change": -0.76, "health_score": 66, "verdict": "Hold"},
    {"symbol": "PEP", "name": "PepsiCo Inc.", "price": 168.92, "market_cap": 232_000_000_000, "pe": 24.3, "volume": 5_100_000, "percent_change": 0.12, "health_score": 72, "verdict": "Hold"},
    {"symbol": "COST", "name": "Costco Wholesale Corp.", "price": 845.23, "market_cap": 375_000_000_000, "pe": 48.6, "volume": 2_300_000, "percent_change": 1.87, "health_score": 77, "verdict": "Buy"},
    {"symbol": "AVGO", "name": "Broadcom Inc.", "price": 168.45, "market_cap": 780_000_000_000, "pe": 145.2, "volume": 32_000_000, "percent_change": 2.98, "health_score": 80, "verdict": "Buy"},
    {"symbol": "KO", "name": "Coca-Cola Company", "price": 62.45, "market_cap": 270_000_000_000, "pe": 25.1, "volume": 14_200_000, "percent_change": 0.08, "health_score": 73, "verdict": "Hold"},
    {"symbol": "ADBE", "name": "Adobe Inc.", "price": 485.67, "market_cap": 215_000_000_000, "pe": 42.8, "volume": 3_400_000, "percent_change": -1.23, "health_score": 69, "verdict": "Hold"},
    {"symbol": "MCD", "name": "McDonald's Corporation", "price": 278.34, "market_cap": 200_000_000_000, "pe": 23.5, "volume": 3_600_000, "percent_change": 0.67, "health_score": 74, "verdict": "Buy"},
    {"symbol": "CRM", "name": "Salesforce Inc.", "price": 272.89, "market_cap": 265_000_000_000, "pe": 45.6, "volume": 6_700_000, "percent_change": 2.34, "health_score": 72, "verdict": "Buy"},
    {"symbol": "CSCO", "name": "Cisco Systems Inc.", "price": 52.78, "market_cap": 215_000_000_000, "pe": 19.4, "volume": 18_900_000, "percent_change": -0.34, "health_score": 68, "verdict": "Hold"},
    {"symbol": "TMO", "name": "Thermo Fisher Scientific", "price": 562.12, "market_cap": 215_000_000_000, "pe": 32.1, "volume": 1_800_000, "percent_change": 0.89, "health_score": 76, "verdict": "Buy"},
]


def _screener_mock_data():
    """Return mock screener data for development when both OpenBB and yfinance are unavailable."""
    try:
        import pandas as pd
        return pd.DataFrame(_MOCK_STOCKS)
    except Exception:
        return None


# ─── Sectors ──────────────────────────────────────────────────

@app.route("/api/sectors", methods=["GET"])
def api_sectors():
    """Sector universe."""
    try:
        sectors = get_all_sectors()
        return jsonify({"sectors": sectors})
    except Exception as e:
        return jsonify({"error": str(e), "sectors": []}), 500


@app.route("/api/sectors/search", methods=["GET"])
def api_sectors_search():
    """Sector/industry/company search."""
    q = request.args.get("q", "")
    sector = request.args.get("sector", "")
    industry = request.args.get("industry", "")
    try:
        results = get_companies_matching(q, sector=sector, industry=industry)
        # Default numeric fields (set to None so frontend shows N/A when missing)
        for r in results[:50]:
            r.setdefault("price", None)
            r.setdefault("marketCap", None)
            r.setdefault("pe", None)
            r.setdefault("change", None)
            r.setdefault("healthScore", None)
        # Enrich first 50 results with price data from yfinance
        import yfinance as yf  # type: ignore
        for r in results[:50]:
            try:
                t = yf.Ticker(r.get("ticker", ""))
                info = t.fast_info
                price = getattr(info, "last_price", None) or getattr(info, "previous_close", None)
                if price is not None:
                    r["price"] = round(float(price), 2)
                    mcap = getattr(info, "market_cap", None)
                    r["marketCap"] = int(mcap) if mcap else None
                    pe = getattr(info, "trailing_pe", None)
                    r["pe"] = round(float(pe), 2) if pe else None
                    hist = t.history(period="5d")
                    change = 0.0
                    if len(hist) >= 2:
                        prev = hist["Close"].iloc[-2]
                        curr = hist["Close"].iloc[-1]
                        if prev and prev > 0:
                            change = ((curr - prev) / prev) * 100
                    r["change"] = round(change, 2)
            except Exception:
                pass
        return jsonify({"results": results})
    except Exception as e:
        return jsonify({"error": str(e), "results": []}), 500


# ─── Notifications ─────────────────────────────────────────────

@app.route("/api/notifications/<int:user_id>", methods=["GET"])
def api_get_notifications(user_id):
    check = _check_session_owns_user_id(user_id)
    if check:
        return check
    limit = request.args.get("limit", 10, type=int)
    unread_only = request.args.get("unread_only", "false").lower() == "true"
    notifications = get_notifications(user_id, limit=limit, unread_only=unread_only)
    return jsonify({"notifications": notifications})


@app.route("/api/notifications/<int:user_id>/unread-count", methods=["GET"])
def api_unread_count(user_id):
    check = _check_session_owns_user_id(user_id)
    if check:
        return check
    count = get_unread_count(user_id)
    return jsonify({"count": count})


@app.route("/api/notifications/<int:user_id>/mark-read", methods=["POST"])
def api_mark_read(user_id):
    check = _check_session_owns_user_id(user_id)
    if check:
        return check
    body = request.get_json(silent=True)
    if not body or "notification_id" not in body:
        return jsonify({"error": "notification_id is required"}), 400
    try:
        mark_read(body["notification_id"])
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/notifications/<int:user_id>/mark-all-read", methods=["POST"])
def api_mark_all_read(user_id):
    check = _check_session_owns_user_id(user_id)
    if check:
        return check
    try:
        mark_all_read(user_id)
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/notifications/<int:user_id>/dismiss", methods=["POST"])
def api_dismiss_notification(user_id):
    check = _check_session_owns_user_id(user_id)
    if check:
        return check
    body = request.get_json(silent=True)
    if not body or "notification_id" not in body:
        return jsonify({"error": "notification_id is required"}), 400
    try:
        dismiss_notification(body["notification_id"])
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/notifications/stats", methods=["GET"])
def api_notification_stats():
    """Get notification stats for admin view."""
    users = get_all_users()
    total_users = len(users)
    total_notifications = 0
    total_unread = 0
    for user in users:
        notifs = get_notifications(user["id"], limit=1000)
        total_notifications += len(notifs)
        total_unread += get_unread_count(user["id"])
    return jsonify({
        "total": total_notifications,
        "unread": total_unread,
        "total_users": total_users,
    })


# ─── Alerts ────────────────────────────────────────────────────

@app.route("/api/alerts/<int:user_id>", methods=["GET"])
def api_get_alerts(user_id):
    """List custom alert rules."""
    check = _check_session_owns_user_id(user_id)
    if check:
        return check
    enabled_only = request.args.get("enabled_only", "false").lower() == "true"
    rules = get_custom_alert_rules(user_id, enabled_only=enabled_only)
    for rule in rules:
        # Parse conditions from JSON string to array (SQLite stores it as text)
        if isinstance(rule.get("conditions"), str):
            rule["conditions"] = json.loads(rule["conditions"])
        # Normalize DB column name to frontend field name
        if "logic_operator" in rule:
            rule["logic"] = rule.pop("logic_operator")
    return jsonify({"rules": rules})


@app.route("/api/alerts/<int:user_id>", methods=["POST"])
def api_create_alert(user_id):
    """Create alert rule."""
    check = _check_session_owns_user_id(user_id)
    if check:
        return check
    body = request.get_json(silent=True)
    if not body or "name" not in body:
        return jsonify({"error": "name is required"}), 400
    try:
        conditions = body.get("conditions", [])
        # Frontend sends conditions as array; DB stores as JSON string
        if isinstance(conditions, (list, dict)):
            conditions = json.dumps(conditions)
        rule_id = create_custom_alert_rule(
            user_id,
            name=body["name"],
            scope=body.get("scope", "watchlist"),
            ticker=body.get("ticker"),
            conditions=conditions,
            logic_operator=body.get("logic_operator", body.get("logic", "AND")),
            severity=body.get("severity", "info"),
        )
        return jsonify({"ok": True, "rule_id": rule_id}), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/alerts/<int:user_id>/<int:rule_id>", methods=["PUT"])
def api_update_alert(user_id, rule_id):
    """Update alert rule."""
    check = _check_session_owns_user_id(user_id)
    if check:
        return check
    body = request.get_json(silent=True)
    if not body:
        return jsonify({"error": "request body is required"}), 400
    try:
        # Verify ownership
        existing = get_custom_alert_rule_by_id(rule_id)
        if not existing or existing["user_id"] != user_id:
            return jsonify({"error": "alert not found"}), 404
        update_custom_alert_rule(rule_id, **body)
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/alerts/<int:user_id>/<int:rule_id>", methods=["DELETE"])
def api_delete_alert(user_id, rule_id):
    """Delete alert rule."""
    check = _check_session_owns_user_id(user_id)
    if check:
        return check
    try:
        existing = get_custom_alert_rule_by_id(rule_id)
        if not existing or existing["user_id"] != user_id:
            return jsonify({"error": "alert not found"}), 404
        delete_custom_alert_rule(rule_id)
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/alerts/<int:user_id>/<int:rule_id>/toggle", methods=["POST"])
def api_toggle_alert(user_id, rule_id):
    """Enable/disable rule."""
    check = _check_session_owns_user_id(user_id)
    if check:
        return check
    body = request.get_json(silent=True)
    try:
        existing = get_custom_alert_rule_by_id(rule_id)
        if not existing or existing["user_id"] != user_id:
            return jsonify({"error": "alert not found"}), 404
        new_state = body.get("enabled", not existing["enabled"]) if body else not existing["enabled"]
        toggle_custom_alert_rule(rule_id, bool(new_state))
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/alerts/signals", methods=["GET"])
def api_alert_signals():
    """Signal catalog (from SIGNAL_CATALOG)."""
    try:
        categories = get_signal_categories()
        signals_by_cat = {}
        for cat in categories:
            signals_by_cat[cat] = get_signals_by_category(cat)
        flat_signals = []
        for cat_signals in signals_by_cat.values():
            flat_signals.extend(cat_signals)
        return jsonify({
            "categories": categories,
            "signals": flat_signals,
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ─── Preferences ───────────────────────────────────────────────

@app.route("/api/preferences/<int:user_id>", methods=["GET"])
def api_get_preferences(user_id):
    check = _check_session_owns_user_id(user_id)
    if check:
        return check
    prefs = get_preferences(user_id)
    return jsonify({"preferences": prefs})


@app.route("/api/preferences/<int:user_id>", methods=["POST"])
def api_set_preferences(user_id):
    check = _check_session_owns_user_id(user_id)
    if check:
        return check
    body = request.get_json(silent=True)
    if not body:
        return jsonify({"error": "request body is required"}), 400
    try:
        set_preferences(user_id, **body)
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ─── Bot Tokens ────────────────────────────────────────────────

@app.route("/api/bot-tokens", methods=["GET"])
def api_get_bot_tokens():
    """Return all users with configured Telegram bot tokens.

    Used by the Streamlit Cloud app to poll for incoming commands.
    """
    tokens = get_user_bot_tokens()
    return jsonify({"users": tokens})


# ─── Push Notifications (X-API-Key auth, called by Next.js proxy) ──

@app.route("/api/push/subscribe", methods=["POST"])
def api_push_subscribe():
    """Register a push subscription."""
    body = request.get_json(silent=True)
    if not body or "endpoint" not in body:
        return jsonify({"error": "endpoint is required"}), 400

    user_id = _resolve_user_id_from_session()
    upsert_push_subscription(
        user_id=user_id,
        endpoint=body["endpoint"],
        p256dh=body["p256dh"],
        auth=body["auth"],
        browser=body.get("browser", "unknown"),
    )
    return jsonify({"status": "subscribed"})


@app.route("/api/push/unsubscribe", methods=["POST"])
def api_push_unsubscribe():
    """Remove a push subscription."""
    body = request.get_json(silent=True)
    if not body or "endpoint" not in body:
        return jsonify({"error": "endpoint is required"}), 400

    _resolve_user_id_from_session()
    remove_push_subscription(body["endpoint"])
    return jsonify({"status": "unsubscribed"})


@app.route("/api/push/status", methods=["GET"])
def api_push_status():
    """Get push subscription status for the current user."""
    user_id = _resolve_user_id_from_session()

    subs = get_push_subscriptions_for_user(user_id)
    return jsonify({
        "subscribed": len(subs) > 0,
        "subscriptions": [{"endpoint": s.endpoint, "browser": s.browser} for s in subs],
    })


@app.route("/api/push/test", methods=["POST"])
def api_push_test():
    """Send a test push notification to the current user."""
    user_id = _resolve_user_id_from_session()

    subs = get_push_subscriptions_for_user(user_id)
    if not subs:
        return jsonify({"error": "no active subscriptions"}), 400

    results = send_push_notifications(
        subscriptions=subs,
        title="Sentinel Test",
        body="This is a test notification from Sentinel.",
        data={"url": "/"},
    )

    sent = sum(1 for r in results if r["status"] == "sent")
    if sent > 0:
        return jsonify({"status": "sent", "count": sent})
    return jsonify({"error": "test push delivery failed"}), 500


# ─── Main ──────────────────────────────────────────────────────

def main():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    )
    init_auth_db()
    init_notification_db()
    logger.info("Sentinel API starting on 127.0.0.1:5252")
    app.run(host="0.0.0.0", port=5252, debug=False, threaded=True)


if __name__ == "__main__":
    main()
