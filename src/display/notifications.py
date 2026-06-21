"""
Notification UI components for the Sentinel dashboard.

Renders the auth forms (login/register), notification bell with unread badge,
notification drawer, preferences panel, and Telegram setup instructions.

Follows the existing render_* pattern in src/display/ — top-level functions
that take data and call st.markdown(..., unsafe_allow_html=True).
"""

import streamlit as st
from typing import Dict, List

from src.data.auth_db import (
    register_user,
    login_user,
    needs_migration,
    legacy_watchlist_count,
    migrate_legacy_watchlist,
)
from src.data.notification_db import (
    get_unread_count,
    get_notifications,
    get_preferences,
    set_preferences,
    mark_read,
    mark_all_read,
    dismiss_notification,
)
from src.notifications.telegram_bot import (
    discover_chat_id,
    send_test_message as send_telegram_test,
    clear_polling_state,
)

# ─── Remote DB Routing ─────────────────────────────────────
# Routes auth and preferences through the VPS API when configured,
# falling back to local SQLite. Ensures Streamlit Cloud and the
# VPS daemon share the same user/accounts database.

def _remote():
    """Lazy-lookup the remote DB client (avoid import-time circular deps)."""
    from src.data.remote_db import get_remote_db
    return get_remote_db()


def _remote_get_preferences(user_id: int) -> Dict:
    """Get preferences through remote API if available."""
    remote = _remote()
    if remote:
        return remote.get_preferences(user_id)
    return get_preferences(user_id)


def _remote_get_notifications(user_id: int, **kwargs) -> List[Dict]:
    """Get notifications through remote API if available."""
    remote = _remote()
    if remote:
        return remote.get_notifications(user_id, **kwargs)
    return get_notifications(user_id, **kwargs)


def _remote_get_unread_count(user_id: int) -> int:
    """Get unread count through remote API if available."""
    remote = _remote()
    if remote:
        return remote.get_unread_count(user_id)
    return get_unread_count(user_id)


# ─── Auth UI ─────────────────────────────────────────────────

def render_auth_ui() -> None:
    """Render login/register forms in the sidebar.

    If user is already logged in (st.session_state.user), shows welcome
    message and sign-out. Otherwise shows compact login/register expander.
    """
    user = st.session_state.get("user")

    if user is not None:
        # Logged in — show welcome + sign out
        st.markdown(
            f'<div style="padding: 8px 0;">'
            f'<span style="color: #8B949E;">👤 </span>'
            f'<span style="color: #E6EDF3; font-weight: 500;">{user["display_name"]}</span>'
            f'</div>',
            unsafe_allow_html=True,
        )
        if st.button("Sign Out", use_container_width=True, key="sign_out"):
            # Delete persistent session from DB
            token = st.session_state.get("session_token")
            if token:
                from src.data.auth_db import delete_session
                delete_session(token)
            # If signed in via Google OAuth, clear the OIDC state too
            try:
                if st.user.is_logged_in:
                    st.logout()
            except AttributeError:
                pass  # OAuth not configured, skip
            st.session_state.user = None
            st.session_state.session_token = None
            st.session_state.watchlist = []
            st.query_params.clear()
            st.rerun()
        return

    # Not logged in — show Google login + login/register expander
    # ── Google OAuth 按钮 ──────────────────────────────────
    # Only show the Google button when OAuth credentials are configured
    # (not placeholder values). The import check prevents the
    # StreamlitMissingAuthlibError when Authlib isn't installed.
    _google_configured = False
    try:
        import authlib  # noqa: F401
        _google_cfg = st.secrets.get("auth", {}).get("google", {})
        _cid = _google_cfg.get("client_id", "")
        _google_configured = bool(_cid) and "REPLACE" not in _cid
    except ImportError:
        pass

    if _google_configured:
        st.markdown(
            '<p style="color: #8B949E; font-size: 0.8rem; margin-bottom: 4px;">Quick sign in:</p>',
            unsafe_allow_html=True,
        )
        if st.button(
            "🔵 Sign in with Google",
            use_container_width=True,
            key="google_login_btn",
            help="Sign in instantly using your Google account — no password needed.",
        ):
            st.login("google")

    st.markdown(
        '<p style="text-align: center; color: #484F58; font-size: 0.75rem; margin: 8px 0;">— or use a password —</p>',
        unsafe_allow_html=True,
    )

    with st.expander("🔐 Sign In / Register", expanded=False):
        auth_tab = st.radio(
            "Account",
            ["Sign In", "Register"],
            horizontal=True,
            label_visibility="collapsed",
            key="auth_tab",
        )

        if auth_tab == "Sign In":
            _render_login_form()
        else:
            _render_register_form()


def _render_login_form() -> None:
    """Compact login form."""
    username = st.text_input("Username", key="login_username", placeholder="username")
    password = st.text_input("Password", type="password", key="login_password", placeholder="••••••••")

    col1, col2 = st.columns([1, 2])
    with col1:
        if st.button("Sign In", use_container_width=True, key="login_btn"):
            if not username or not password:
                st.error("Enter username and password.")
            else:
                remote = _remote()
                if remote:
                    result = remote.login_user(username, password)
                else:
                    result = login_user(username, password)
                if result:
                    st.session_state.user = result
                    # Session token comes from remote API or local create_session
                    token = result.get("_session_token")
                    if not token:
                        from src.data.auth_db import create_session
                        token = create_session(result["id"])
                    st.session_state.session_token = token
                    st.query_params["session"] = token
                    # Load user watchlist (always through remote-aware routing)
                    from app import _remote_load_watchlist
                    st.session_state.watchlist = _remote_load_watchlist(result["id"])
                    st.rerun()
                else:
                    st.error("Invalid username or password.")


def _render_register_form() -> None:
    """Compact registration form with legacy migration support."""
    username = st.text_input("Username", key="reg_username", placeholder="pick a username")
    display_name = st.text_input("Display Name (optional)", key="reg_display", placeholder="John")
    password = st.text_input("Password", type="password", key="reg_password", placeholder="min 4 characters")
    password2 = st.text_input("Confirm Password", type="password", key="reg_password2", placeholder="repeat password")

    # Migration banner
    if needs_migration():
        count = legacy_watchlist_count()
        st.info(f"📋 A shared watchlist with **{count}** tickers exists. Register to claim it.")

    if st.button("Create Account", use_container_width=True, key="register_btn"):
        if not username or not password:
            st.error("Username and password are required.")
        elif len(password) < 4:
            st.error("Password must be at least 4 characters.")
        elif password != password2:
            st.error("Passwords do not match.")
        else:
            remote = _remote()
            if remote:
                user = remote.register_user(username, password, display_name=display_name or None)
            else:
                user = register_user(username, password, display_name=display_name or None)
            if user:
                # Migrate legacy watchlist if applicable
                if needs_migration():
                    migrated = migrate_legacy_watchlist(user["id"])
                    if migrated > 0:
                        st.success(f"Claimed {migrated} tickers from the shared watchlist!")

                st.session_state.user = user
                # Session token comes from remote API or local create_session
                token = user.get("_session_token")
                if not token:
                    from src.data.auth_db import create_session
                    token = create_session(user["id"])
                st.session_state.session_token = token
                st.query_params["session"] = token
                from app import _remote_load_watchlist
                st.session_state.watchlist = _remote_load_watchlist(user["id"])
                st.rerun()
            else:
                st.error("Username already taken. Choose another.")


# ─── Notification Bell ───────────────────────────────────────

def render_notification_bell() -> None:
    """Render a bell icon in the sidebar with unread count badge.

    Shows nothing if the user is not logged in.
    """
    user = st.session_state.get("user")
    if not user:
        return

    unread = _remote_get_unread_count(user["id"])

    badge_html = ""
    if unread > 0:
        badge_html = (
            f'<span style="'
            f'background: #DA3633; color: #fff; font-size: 0.65rem; '
            f'padding: 2px 6px; border-radius: 10px; margin-left: 4px; '
            f'vertical-align: middle;'
            f'">{unread}</span>'
        )

    st.markdown("---")
    st.markdown(
        f'<div style="padding: 4px 0; cursor: pointer;">'
        f'🔔 <span style="color: #E6EDF3; font-weight: 500;">Notifications</span>'
        f'{badge_html}'
        f'</div>',
        unsafe_allow_html=True,
    )

    # Show most recent notifications in an expander
    with st.expander(f"Recent ({unread} unread)", expanded=False):
        notifications = _remote_get_notifications(user["id"], limit=10)
        if not notifications:
            st.markdown(
                '<p style="color: #484F58; font-size: 0.8rem;">No notifications yet. '
                'We\'ll alert you when your watched stocks have meaningful changes.</p>',
                unsafe_allow_html=True,
            )
        else:
            for n in notifications:
                render_notification_card(n)

            if unread > 0:
                if st.button("Mark All Read", use_container_width=True, key="mark_all_read"):
                    mark_all_read(user["id"])
                    st.rerun()


def render_notification_card(n: Dict) -> None:
    """Render a single notification as a compact card."""
    severity_colors = {
        "critical": "#DA3633",
        "warning": "#D29922",
        "info": "#58A6FF",
    }
    severity_icons = {
        "critical": "🚨",
        "warning": "⚠️",
        "info": "ℹ️",
    }
    color = severity_colors.get(n.get("severity", "info"), "#58A6FF")
    icon = severity_icons.get(n.get("severity", "info"), "ℹ️")

    read_style = "opacity: 0.6;" if n.get("is_read") else ""
    ticker_badge = f'<span style="color: #58A6FF; font-weight: 600;">{n.get("ticker", "")}</span>' if n.get("ticker") else ""

    st.markdown(
        f'<div style="border-left: 3px solid {color}; padding: 6px 10px; '
        f'margin: 4px 0; background: rgba(255,255,255,0.03); '
        f'border-radius: 4px; {read_style}">'
        f'<div style="font-size: 0.8rem; color: #8B949E; margin-bottom: 2px;">'
        f'{icon} {ticker_badge} &nbsp; {n.get("title", "")}'
        f'</div>'
        f'<div style="font-size: 0.72rem; color: #8B949E;">'
        f'{n.get("body", "")}'
        f'</div>'
        f'</div>',
        unsafe_allow_html=True,
    )

    if not n.get("is_read"):
        col1, col2 = st.columns([1, 3])
        with col1:
            if st.button("✓ Read", key=f"read_{n['id']}", use_container_width=True):
                mark_read(n["id"])
                st.rerun()
        with col2:
            if st.button("✕ Dismiss", key=f"dismiss_{n['id']}", use_container_width=True):
                dismiss_notification(n["id"])
                st.rerun()


# ─── Notification Preferences ────────────────────────────────

def render_notification_preferences() -> None:
    """Render notification preferences panel.

    Shows toggles for each trigger type, Telegram connection status,
    and check interval. Only visible when a user is logged in.
    """
    user = st.session_state.get("user")
    if not user:
        return

    st.markdown("---")
    st.markdown(
        '<p style="color: #8B949E; font-size: 0.75rem; font-weight: 600;">⚙️ Alert Settings</p>',
        unsafe_allow_html=True,
    )

    prefs = _remote_get_preferences(user["id"])

    with st.expander("Configure", expanded=False):
        # Trigger toggles
        st.markdown('<p style="color: #E6EDF3; font-size: 0.8rem;">Notify me when:</p>',
                    unsafe_allow_html=True)

        new_prefs = {}

        health = st.checkbox("Health Score changes", value=bool(prefs.get("health_change", 1)),
                             key="pref_health")
        new_prefs["health_change"] = 1 if health else 0

        verdict = st.checkbox("Valuation verdict changes", value=bool(prefs.get("verdict_change", 1)),
                              key="pref_verdict")
        new_prefs["verdict_change"] = 1 if verdict else 0

        risk = st.checkbox("Risk flag changes", value=bool(prefs.get("risk_flag_change", 1)),
                           key="pref_risk")
        new_prefs["risk_flag_change"] = 1 if risk else 0

        zscore = st.checkbox("Z-Score zone changes", value=bool(prefs.get("zscore_zone_change", 1)),
                             key="pref_zscore")
        new_prefs["zscore_zone_change"] = 1 if zscore else 0

        fscore = st.checkbox("F-Score changes", value=bool(prefs.get("fscore_change", 1)),
                             key="pref_fscore")
        new_prefs["fscore_change"] = 1 if fscore else 0

        st.markdown("---")

        # Check interval
        interval = st.select_slider(
            "Check every",
            options=[1, 2, 4, 6, 8, 12, 24],
            value=prefs.get("check_interval_hours", 2),
            format_func=lambda h: f"{h}h",
            key="pref_interval",
        )
        new_prefs["check_interval_hours"] = interval

        # ── Telegram notifications ────────────────────────
        telegram_bot_token = prefs.get("telegram_bot_token", "")
        telegram_chat_id = prefs.get("telegram_chat_id", "")
        is_telegram_connected = bool(telegram_bot_token and telegram_chat_id)

        st.markdown('<p style="color: #E6EDF3; font-size: 0.8rem; margin-top: 12px;">🤖 Telegram</p>',
                    unsafe_allow_html=True)

        if is_telegram_connected:
            telegram_on = st.checkbox("Send alerts to Telegram",
                                      value=bool(prefs.get("telegram_enabled", 0)),
                                      key="pref_telegram")
            new_prefs["telegram_enabled"] = 1 if telegram_on else 0
            st.success("✅ Telegram connected")
        else:
            st.info("Go to ⚙️ **Settings** to connect Telegram.")

        if st.button("Save Settings", use_container_width=True, key="save_prefs"):
            remote = _remote()
            if remote:
                remote.set_preferences(user["id"], **new_prefs)
            else:
                set_preferences(user["id"], **new_prefs)
            st.success("Settings saved.")
            st.rerun()


# ─── Full Notification List ──────────────────────────────────

def render_notification_list() -> None:
    """Render the full notification history page with filters."""
    user = st.session_state.get("user")
    if not user:
        st.warning("Sign in to view notifications.")
        return

    st.subheader("🔔 Notification History")

    col1, col2, col3 = st.columns(3)
    with col1:
        show_filter = st.selectbox("Show", ["Unread", "All"], key="notif_filter")
    with col2:
        severity_filter = st.selectbox("Severity", ["All", "critical", "warning", "info"], key="notif_severity")
    with col3:
        ticker_filter = st.text_input("Ticker", key="notif_ticker", placeholder="e.g. AAPL")

    unread_only = show_filter == "Unread"
    severity = None if severity_filter == "All" else severity_filter
    ticker = ticker_filter.strip().upper() if ticker_filter.strip() else None

    notifications = get_notifications(
        user["id"], limit=100, unread_only=unread_only,
        ticker=ticker, severity=severity,
    )

    if not notifications:
        st.markdown(
            '<p style="color: #484F58; padding: 20px;">No notifications match your filters.</p>',
            unsafe_allow_html=True,
        )
        return

    for n in notifications:
        render_notification_card(n)


# ─── Settings Page ───────────────────────────────────────────

def render_settings_page() -> None:
    """Render the full Settings page with Telegram setup and notification prefs.

    Two sections:
    1. Telegram bot setup (token, connection status, test)
    2. Notification preferences (what triggers, how often)
    """
    st.markdown('<h2 style="color: #58A6FF;">⚙️ Settings</h2>', unsafe_allow_html=True)

    user = st.session_state.get("user")
    if not user:
        st.warning("Sign in to configure settings.")
        return

    prefs = _remote_get_preferences(user["id"])

    # ─── Section: Telegram Notifications ──────────────────
    st.markdown("---")
    st.markdown("### 🤖 Telegram Notifications")
    st.markdown(
        "Receive Sentinel alerts directly on Telegram. "
        "You provide your own bot token (free via @BotFather). "
        "Runs 24/7 through our daemon — even when you're not using the dashboard."
    )

    _telegram_token = prefs.get("telegram_bot_token", "")
    _telegram_chat_id = prefs.get("telegram_chat_id", "")
    _has_token = bool(_telegram_token)
    _has_chat_id = bool(_telegram_chat_id)

    if _has_token and _has_chat_id:
        # ── STATE: Connected ────────────────────────────
        st.success(
            f"✅ **Connected!**\n\n"
            f"Chat ID: `{_telegram_chat_id}`\n\n"
            f"You're receiving alerts and commands via Telegram."
        )

        col_test, col_disconnect = st.columns([1, 3])
        with col_test:
            if st.button("📨 Send Test Alert", use_container_width=True, key="test_telegram"):
                if send_telegram_test(bot_token=_telegram_token, chat_id=_telegram_chat_id):
                    st.success("Test message sent! Check your Telegram.")
                else:
                    st.error("Failed to send test message. The bot may be disabled or blocked.")
        with col_disconnect:
            if st.button("🗑️ Disconnect", use_container_width=True, key="clear_telegram"):
                remote = _remote()
                if remote:
                    remote.set_preferences(
                        user["id"],
                        telegram_bot_token="",
                        telegram_enabled=0,
                    )
                else:
                    set_preferences(
                        user["id"],
                        telegram_bot_token="",
                        telegram_enabled=0,
                    )
                clear_polling_state(user["id"])
                st.success("Telegram disconnected.")
                st.rerun()

    elif _has_token and not _has_chat_id:
        # ── STATE: Token saved, waiting for chat_id ──────
        st.warning(
            "⚠️ Bot token saved but not linked yet.\n\n"
            "Send any message to your bot on Telegram, then come back to retry."
        )

        col_retry = st.container()
        with col_retry:
            if st.button("🔄 Retry Discovery", use_container_width=True, key="retry_telegram_link"):
                found_id = discover_chat_id(_telegram_token, user["id"])
                if found_id:
                    remote = _remote()
                    if remote:
                        remote.link_telegram(user["id"], found_id)
                    else:
                        from src.data.auth_db import link_telegram
                        link_telegram(user["id"], found_id)
                    st.success(
                        f"✅ Linked! Your Telegram is now connected as `{found_id}`.\n\n"
                        f"You should receive a welcome message on Telegram shortly."
                    )
                    st.rerun()
                else:
                    st.info("Still no message detected. Please send a message to your bot first.")

        st.caption(
            "**Or use `/link`:** Open your bot in Telegram and send "
            "`/link <your-username>` to connect automatically."
        )

    else:
        # ── STATE: Not connected ─────────────────────────
        st.markdown("""
        **Simple 3-step setup:**
        1. Open [@BotFather](https://t.me/BotFather) on Telegram
        2. Send `/newbot` and follow the prompts to create your bot
        3. Paste the token below and click Connect
        """)

        with st.form("telegram_setup_form"):
            bot_token_input = st.text_input(
                "Your Bot Father Token",
                key="settings_telegram_token",
                placeholder="1234567890:ABCdefGHI-jklMNOpqrsTUVwxyz",
                help="Got it from @BotFather on Telegram",
            )
            submitted = st.form_submit_button("🔌 Connect Telegram", use_container_width=True)
            if submitted:
                if not bot_token_input.strip():
                    st.error("Please enter your bot token.")
                else:
                    token = bot_token_input.strip()
                    remote = _remote()
                    if remote:
                        remote.set_preferences(
                            user["id"],
                            telegram_bot_token=token,
                            telegram_enabled=1,
                        )
                    else:
                        set_preferences(
                            user["id"],
                            telegram_bot_token=token,
                            telegram_enabled=1,
                        )
                    # Try auto-discovery — user may have already messaged the bot
                    found_id = discover_chat_id(token, user["id"])
                    if found_id:
                        from src.data.auth_db import link_telegram
                        link_telegram(user["id"], found_id)
                        st.success(
                            f"✅ Connected! Chat ID: `{found_id}`\n\n"
                            f"You should receive a welcome message on Telegram shortly."
                        )
                        st.rerun()
                    else:
                        st.info(
                            "⚠️ Token accepted. Now send any message to your bot on Telegram "
                            "so we can complete the connection."
                        )
                        st.rerun()

    # ─── Section: Notification Preferences ──────────────────
    st.markdown("---")
    st.markdown("### 🔔 What to Notify Me About")

    new_prefs = {}

    st.markdown("**Notify me when:**")

    col_left, col_right = st.columns(2)
    with col_left:
        health = st.checkbox(
            "💊 Health Score changes (≥15 pts)",
            value=bool(prefs.get("health_change", 1)),
            key="settings_health",
            help="The composite health score reflects financial strength across profitability, leverage, and efficiency.",
        )
        new_prefs["health_change"] = 1 if health else 0

        verdict = st.checkbox(
            "📊 Valuation verdict changes",
            value=bool(prefs.get("verdict_change", 1)),
            key="settings_verdict",
            help="When a stock moves between Undervalued, Fairly Valued, or Overvalued.",
        )
        new_prefs["verdict_change"] = 1 if verdict else 0

        risk = st.checkbox(
            "🔴 Risk flag changes",
            value=bool(prefs.get("risk_flag_change", 1)),
            key="settings_risk",
            help="When new red flags are detected or existing ones are resolved.",
        )
        new_prefs["risk_flag_change"] = 1 if risk else 0

    with col_right:
        zscore = st.checkbox(
            "📐 Z-Score zone changes",
            value=bool(prefs.get("zscore_zone_change", 1)),
            key="settings_zscore",
            help="When the bankruptcy risk zone changes (Safe ↔ Grey ↔ Distress).",
        )
        new_prefs["zscore_zone_change"] = 1 if zscore else 0

        fscore = st.checkbox(
            "📋 F-Score changes (≥3 pts)",
            value=bool(prefs.get("fscore_change", 1)),
            key="settings_fscore",
            help="The Piotroski F-Score rates financial health on a 0–9 scale.",
        )
        new_prefs["fscore_change"] = 1 if fscore else 0

    st.markdown("---")

    interval = st.select_slider(
        "Check my watchlist for changes every",
        options=[1, 2, 4, 6, 8, 12, 24],
        value=prefs.get("check_interval_hours", 2),
        format_func=lambda h: f"{h} hour{'s' if h > 1 else ''}",
        key="settings_interval",
    )
    new_prefs["check_interval_hours"] = interval

    min_delta = st.select_slider(
        "Minimum health score change to alert me",
        options=[5, 10, 15, 20, 25, 30],
        value=prefs.get("min_health_delta", 15),
        format_func=lambda d: f"≥{d} points",
        key="settings_min_delta",
    )
    new_prefs["min_health_delta"] = min_delta

    if st.button("💾 Save Preferences", use_container_width=True, key="save_settings_prefs"):
        set_preferences(user["id"], **new_prefs)
        st.success("Preferences saved!")
        st.rerun()
