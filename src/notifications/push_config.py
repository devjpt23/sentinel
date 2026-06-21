"""VAPID configuration for web push notifications."""

import os
import logging

logger = logging.getLogger(__name__)

VAPID_PUBLIC_KEY = os.environ.get("VAPID_PUBLIC_KEY", "")
_raw_private_key = os.environ.get("VAPID_PRIVATE_KEY", "")
VAPID_SUBJECT = os.environ.get("VAPID_SUBJECT", "mailto:admin@sentinel-trader.com")

# Normalize private key: wrap as PEM if it's a raw base64 key (no PEM header)
if _raw_private_key and not _raw_private_key.startswith("-----BEGIN"):
    VAPID_PRIVATE_KEY = f"-----BEGIN EC PRIVATE KEY-----\n{_raw_private_key}\n-----END EC PRIVATE KEY-----"
else:
    VAPID_PRIVATE_KEY = _raw_private_key

PUSH_ENABLED = bool(VAPID_PUBLIC_KEY and VAPID_PRIVATE_KEY)

if not PUSH_ENABLED:
    logger.warning(
        "VAPID keys not configured — push notifications disabled. "
        "Set VAPID_PUBLIC_KEY and VAPID_PRIVATE_KEY environment variables. "
        "Run: python scripts/generate_vapid_keys.py"
    )

def validate_vapid_keys() -> bool:
    """Check VAPID keys are present and non-empty. Call at daemon startup."""
    if not VAPID_PUBLIC_KEY or not VAPID_PRIVATE_KEY:
        logger.error("VAPID keys missing — push notifications will not work")
        return False
    if len(VAPID_PRIVATE_KEY) < 20:
        logger.error("VAPID_PRIVATE_KEY appears truncated — push notifications will not work")
        return False
    return True
