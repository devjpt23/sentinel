"""
Sentinel HTTP API — remote data access for Streamlit Cloud.

A lightweight Flask server that exposes the VPS SQLite database over HTTP.
All endpoints require the X-API-Key header. The server binds to localhost
only — expose it externally via a reverse proxy or tunnel.

Usage:
    SENTINEL_API_KEY=my-secret python -m src.api.server
"""

import logging
import os
import secrets
import time
import threading

from flask import Flask, request, jsonify

from src.data.auth_db import (
    init_auth_db,
    get_user,
    register_user,
    login_user,
    create_session,
)
from src.data.watchlist_db import (
    load_user_watchlist,
    add_user_ticker,
    remove_user_ticker,
)
from src.data.notification_db import (
    init_notification_db,
    get_notifications,
    get_unread_count,
    get_preferences,
    set_preferences,
)

logger = logging.getLogger(__name__)

API_KEY = os.environ.get("SENTINEL_API_KEY", "")
if not API_KEY:
    logger.error("SENTINEL_API_KEY environment variable is not set")

app = Flask(__name__)


# ─── Rate Limiting ─────────────────────────────────────────────

_rate_limits: dict[str, list[float]] = {}
_rate_lock = threading.Lock()

MAX_REQUESTS_PER_MINUTE = 60


def _check_rate_limit(ip: str) -> bool:
    """Return True if the request is within rate limits."""
    now = time.time()
    with _rate_lock:
        # Clean old entries
        _rate_limits[ip] = [t for t in _rate_limits.get(ip, []) if now - t < 60]
        if len(_rate_limits[ip]) >= MAX_REQUESTS_PER_MINUTE:
            return False
        _rate_limits[ip].append(now)
        return True


# ─── Middleware ────────────────────────────────────────────────

@app.before_request
def before_request():
    """Validate API key and check rate limit on every request."""
    if not API_KEY:
        return jsonify({"error": "server misconfiguration"}), 500

    provided = request.headers.get("X-API-Key", "")
    if not provided or not secrets.compare_digest(provided, API_KEY):
        return jsonify({"error": "unauthorized"}), 401

    ip = request.remote_addr or "unknown"
    if not _check_rate_limit(ip):
        return jsonify({"error": "rate limit exceeded"}), 429


# ─── Health ────────────────────────────────────────────────────

@app.route("/api/health", methods=["GET"])
def health():
    return jsonify({"ok": True})


# ─── Watchlist ─────────────────────────────────────────────────

@app.route("/api/watchlist/<int:user_id>", methods=["GET"])
def api_get_watchlist(user_id):
    tickers = load_user_watchlist(user_id)
    return jsonify({"user_id": user_id, "tickers": tickers})


@app.route("/api/watchlist", methods=["POST"])
def api_add_ticker():
    body = request.get_json(silent=True)
    if not body or "user_id" not in body or "ticker" not in body:
        return jsonify({"error": "user_id and ticker are required"}), 400
    try:
        add_user_ticker(body["user_id"], body["ticker"])
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/watchlist/<int:user_id>/<ticker>", methods=["DELETE"])
def api_remove_ticker(user_id, ticker):
    try:
        remove_user_ticker(user_id, ticker)
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ─── Auth ──────────────────────────────────────────────────────

@app.route("/api/user/<int:user_id>", methods=["GET"])
def api_get_user(user_id):
    user = get_user(user_id)
    if not user:
        return jsonify({"error": "user not found"}), 404
    # Strip sensitive fields
    user.pop("password_hash", None)
    user.pop("salt", None)
    return jsonify({"user": user})


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


# ─── Notifications ─────────────────────────────────────────────

@app.route("/api/notifications/<int:user_id>", methods=["GET"])
def api_get_notifications(user_id):
    limit = request.args.get("limit", 10, type=int)
    unread_only = request.args.get("unread_only", "false").lower() == "true"
    notifications = get_notifications(user_id, limit=limit, unread_only=unread_only)
    return jsonify({"notifications": notifications})


@app.route("/api/notifications/<int:user_id>/unread-count", methods=["GET"])
def api_unread_count(user_id):
    count = get_unread_count(user_id)
    return jsonify({"count": count})


# ─── Preferences ───────────────────────────────────────────────

@app.route("/api/preferences/<int:user_id>", methods=["GET"])
def api_get_preferences(user_id):
    prefs = get_preferences(user_id)
    return jsonify({"preferences": prefs})


@app.route("/api/preferences/<int:user_id>", methods=["POST"])
def api_set_preferences(user_id):
    body = request.get_json(silent=True)
    if not body:
        return jsonify({"error": "request body is required"}), 400
    try:
        set_preferences(user_id, **body)
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ─── Main ──────────────────────────────────────────────────────

def main():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    )
    init_auth_db()
    init_notification_db()
    logger.info("Sentinel API starting on 127.0.0.1:5252")
    app.run(host="127.0.0.1", port=5252, debug=False)


if __name__ == "__main__":
    main()
