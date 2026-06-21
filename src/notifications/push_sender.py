"""Send web push notifications using pywebpush."""

import json
import logging
from typing import List, Optional

from src.data.push_db import PushSubscription, deactivate_push_subscription
from src.notifications.push_config import (
    PUSH_ENABLED,
    VAPID_PRIVATE_KEY,
    VAPID_SUBJECT,
)

logger = logging.getLogger(__name__)

try:
    from pywebpush import webpush, WebPushException
except ImportError:
    logger.warning("pywebpush not installed — push notifications unavailable")
    webpush = None
    WebPushException = Exception


def send_push_notifications(
    subscriptions: List[PushSubscription],
    title: str,
    body: str,
    data: Optional[dict] = None,
) -> List[dict]:
    """Send web push to a list of subscriptions. Returns results per subscription.

    Payload is truncated to ~500 chars to stay within browser push limits (~4KB).
    """
    if not PUSH_ENABLED or webpush is None:
        logger.debug("Push disabled or pywebpush unavailable — skipping")
        return []

    body = (body or "")[:500]
    results = []

    for sub in subscriptions:
        try:
            webpush(
                subscription_info={
                    "endpoint": sub.endpoint,
                    "keys": {"p256dh": sub.p256dh, "auth": sub.auth},
                },
                data=json.dumps({"title": title, "body": body, "data": data or {}}),
                vapid_private_key=VAPID_PRIVATE_KEY,
                vapid_claims={"sub": VAPID_SUBJECT},
            )
            results.append({"subscription": sub.id, "status": "sent"})
        except WebPushException as e:
            status_code = getattr(getattr(e, "response", None), "status_code", None)
            if status_code in (404, 410):
                deactivate_push_subscription(sub.id)
                results.append({"subscription": sub.id, "status": "expired"})
            else:
                logger.warning(f"Push delivery failed for sub {sub.id}: {e}")
                results.append({"subscription": sub.id, "status": "failed", "error": str(e)})
        except Exception as e:
            logger.warning(f"Unexpected push error for sub {sub.id}: {e}")
            results.append({"subscription": sub.id, "status": "failed", "error": str(e)})

    return results
