"""
Gmail SMTP email sender for Sentinel notifications.

Sends score-change alerts to users' email addresses via Gmail's SMTP
server using an App Password (no Google Workspace or service account needed).

Uses Python stdlib only — smtplib + email. The App Password is a 16-char
token generated at https://myaccount.google.com/apppasswords (requires 2FA).

Usage:
    from src.notifications.gmail_sender import (
        send_gmail_message,
        format_email_notification,
        send_gmail_test_message,
    )
"""

import logging
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Dict, Optional

import streamlit as st

logger = logging.getLogger(__name__)

# Default sender — overridden via Streamlit secrets or per-user settings
_DEFAULT_SENDER = ""
_DEFAULT_APP_PASSWORD = ""


def _load_defaults() -> None:
    """Load default Gmail credentials from Streamlit secrets once."""
    global _DEFAULT_SENDER, _DEFAULT_APP_PASSWORD
    if not _DEFAULT_SENDER:
        try:
            _DEFAULT_SENDER = st.secrets["gmail"]["sender_email"]
            _DEFAULT_APP_PASSWORD = st.secrets["gmail"]["app_password"]
        except (KeyError, FileNotFoundError):
            pass  # not configured — email channel will be unavailable


def get_default_sender() -> str:
    """Return the default Gmail sender address, or empty string if unconfigured."""
    _load_defaults()
    return _DEFAULT_SENDER


def is_available() -> bool:
    """Return True if the Gmail sender is configured."""
    _load_defaults()
    return bool(_DEFAULT_SENDER and _DEFAULT_APP_PASSWORD)


# ─── Message Sending ───────────────────────────────────────────


def send_gmail_message(
    to_email: str,
    subject: str,
    text_body: str = "",
    html_body: str = "",
    from_email: str = "",
    app_password: str = "",
) -> bool:
    """Send an email via Gmail SMTP.

    Args:
        to_email: Recipient email address.
        subject: Email subject line.
        text_body: Plain text version (fallback for non-HTML clients).
        html_body: Rich HTML version (preferred by most clients).
        from_email: Sender Gmail address (uses default from secrets if empty).
        app_password: 16-char Gmail App Password (uses default from secrets if empty).

    Returns:
        True if the message was accepted by the SMTP server.
    """
    _load_defaults()

    sender = from_email or _DEFAULT_SENDER
    password = app_password or _DEFAULT_APP_PASSWORD

    if not sender or not password:
        logger.warning("Gmail sender not configured — skipping email")
        return False

    # Build the message — prefer multipart so HTML clients get rich rendering
    if html_body:
        msg = MIMEMultipart("alternative")
        msg.attach(MIMEText(text_body or html_body, "plain", "utf-8"))
        msg.attach(MIMEText(html_body, "html", "utf-8"))
    else:
        msg = MIMEText(text_body, "plain", "utf-8")

    msg["From"] = sender
    msg["To"] = to_email
    msg["Subject"] = subject

    for attempt in range(2):
        try:
            with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=10) as server:
                server.login(sender, password)
                server.send_message(msg)
            return True
        except smtplib.SMTPAuthenticationError:
            logger.warning(
                "Gmail authentication failed — check the App Password. "
                "Make sure 2FA is enabled and the password is 16 chars (no spaces)."
            )
            return False
        except (smtplib.SMTPException, OSError) as e:
            logger.warning(f"Gmail send attempt {attempt + 1}/2 failed: {e}")
            if attempt == 0:
                import time
                time.sleep(1.5)

    return False


def send_gmail_test_message(
    to_email: str,
    from_email: str = "",
    app_password: str = "",
) -> bool:
    """Send a test message to verify Gmail delivery is working."""
    subject = "✅ Sentinel Email Notifications Active"
    html_body = f"""
    <div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                max-width: 600px; margin: 0 auto; background: #161B22; color: #C9D1D9;
                border: 1px solid #30363D; border-radius: 12px; padding: 32px;">
        <div style="text-align: center; padding-bottom: 20px;">
            <h2 style="color: #58A6FF; margin: 0;">📊 Sentinel</h2>
            <p style="color: #8B949E; font-size: 14px;">Email notifications are active</p>
        </div>
        <p style="font-size: 16px; line-height: 1.6;">
            You'll now receive alerts when your watched stocks have meaningful changes
            in health scores, risk flags, valuation verdicts, and more.
        </p>
        <hr style="border-color: #30363D; margin: 24px 0;">
        <p style="color: #8B949E; font-size: 12px;">
            Manage your notification preferences in the
            <a href="http://localhost:8501" style="color: #58A6FF;">Sentinel dashboard</a>.
        </p>
    </div>
    """
    text_body = (
        "Sentinel Email Notifications Active\n\n"
        "You'll now receive alerts when your watched stocks have meaningful changes "
        "in health scores, risk flags, valuation verdicts, and more.\n\n"
        "Manage your notification preferences in the Sentinel dashboard."
    )
    return send_gmail_message(
        to_email=to_email,
        subject=subject,
        text_body=text_body,
        html_body=html_body,
        from_email=from_email,
        app_password=app_password,
    )


# ─── Notification Formatting ───────────────────────────────────


def format_email_notification(notification: Dict) -> tuple:
    """Format a notification dict into a rich HTML email body.

    Returns (html_body, subject_line) tuple.
    """
    severity_colors = {
        "critical": "#DA3633",
        "warning": "#D29922",
        "info": "#58A6FF",
    }
    severity_emoji = {
        "critical": "🚨",
        "warning": "⚠️",
        "info": "ℹ️",
    }
    type_labels = {
        "health_change": "Health Score Change",
        "verdict_change": "Valuation Verdict Change",
        "risk_flag_change": "Risk Flag Change",
        "zscore_zone_change": "Z-Score Zone Change",
        "fscore_change": "F-Score Change",
    }

    sev = notification.get("severity", "info")
    ntype = notification.get("type", "")
    ticker = notification.get("ticker", "???")
    title = notification.get("title", "")
    body = notification.get("body", "")
    old_val = notification.get("old_value", "")
    new_val = notification.get("new_value", "")

    color = severity_colors.get(sev, "#58A6FF")
    emoji = severity_emoji.get(sev, "ℹ️")
    type_label = type_labels.get(ntype, ntype)

    subject = f"📊 Sentinel: {ticker} — {title}"

    html = f"""
    <div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                max-width: 600px; margin: 0 auto; background: #161B22; color: #C9D1D9;
                border: 1px solid #30363D; border-radius: 12px; overflow: hidden;">
        <!-- Header bar -->
        <div style="background: {color}; padding: 16px 24px;">
            <h2 style="margin: 0; color: #fff; font-size: 18px;">
                {emoji} {ticker} — {type_label}
            </h2>
        </div>
        <!-- Body -->
        <div style="padding: 24px;">
            <p style="font-size: 16px; line-height: 1.6; margin: 0 0 16px 0;">
                {body}
            </p>"""
    if old_val and new_val:
        html += f"""
            <div style="background: #0D1117; border: 1px solid #30363D; border-radius: 8px;
                        padding: 16px; margin: 16px 0; text-align: center;">
                <span style="color: #8B949E; font-size: 14px;">{old_val}</span>
                <span style="color: #8B949E; margin: 0 12px;">→</span>
                <span style="color: {color}; font-weight: 700; font-size: 16px;">{new_val}</span>
            </div>"""

    html += f"""
        </div>
        <!-- Footer -->
        <div style="border-top: 1px solid #30363D; padding: 16px 24px;
                    background: #0D1117;">
            <p style="color: #8B949E; font-size: 12px; margin: 0;">
                Sent by <a href="http://localhost:8501" style="color: #58A6FF;">Sentinel</a>.
                Manage notifications in your dashboard settings.
            </p>
        </div>
    </div>
    """
    return html, subject
