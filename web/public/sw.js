// Service Worker for web push notifications.
// Served from /sw.js by Next.js public/ directory.

self.addEventListener('push', (event) => {
  try {
    const data = event.data ? event.data.json() : {};
    const title = data.title || 'Sentinel Alert';
    const body = data.body || '';
    const notificationData = data.data || {};
    const severity = notificationData.severity || 'info';
    const ticker = notificationData.ticker || '';
    const notificationType = notificationData.notification_type || 'general';
    const url = notificationData.url || '/';
    const ruleId = notificationData.rule_id || 'sentinel';

    // Tag: group by notification type + ticker so we don't spam
    const tag = `sentinel:${notificationType}:${ticker}`;

    const options = {
      body,
      icon: '/icon-192.png',
      badge: '/badge-72.png',
      tag,
      renotify: true,
      data: { url, ...notificationData },
      actions: [
        { action: 'view', title: 'View' },
        { action: 'view-alerts', title: 'View Alerts' },
        { action: 'dismiss', title: 'Dismiss' },
      ],
    };

    // Critical alerts stay visible until interacted with
    if (severity === 'critical') {
      options.requireInteraction = true;
    }

    event.waitUntil(
      self.registration.showNotification(title, options)
    );
  } catch (err) {
    console.error('[sw] Push event handler error:', err);
    // Fallback: show a generic notification
    event.waitUntil(
      self.registration.showNotification('Sentinel Alert', {
        body: 'A trading alert has been triggered.',
        icon: '/icon-192.png',
        badge: '/badge-72.png',
      })
    );
  }
});

self.addEventListener('notificationclick', (event) => {
  event.notification.close();

  if (event.action === 'view') {
    const url = event.notification.data?.url || '/';
    event.waitUntil(clients.openWindow(url));
  } else if (event.action === 'view-alerts') {
    event.waitUntil(clients.openWindow('/alerts'));
  }
  // 'dismiss' action just closes the notification (handled above)
});

self.addEventListener('pushsubscriptionchange', (event) => {
  console.log('[sw] Push subscription changed — endpoint may need re-subscription');
  // The frontend push-notifications.ts handles re-subscription on next visit
});
