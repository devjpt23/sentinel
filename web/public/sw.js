// Service Worker for web push notifications.
// Served from /sw.js by Next.js public/ directory.

self.addEventListener('push', (event) => {
  const data = event.data ? event.data.json() : {};
  const title = data.title || 'Sentinel Alert';
  const body = data.body || '';
  const url = data.data?.url || '/';

  event.waitUntil(
    self.registration.showNotification(title, {
      body,
      icon: '/icon-192.png',
      badge: '/badge-72.png',
      tag: String(data.data?.rule_id || 'sentinel'),
      renotify: true,
      data: { url },
      actions: [
        { action: 'view', title: 'View' },
        { action: 'dismiss', title: 'Dismiss' },
      ],
    })
  );
});

self.addEventListener('notificationclick', (event) => {
  event.notification.close();
  if (event.action === 'view') {
    event.waitUntil(clients.openWindow(event.notification.data.url));
  }
});

self.addEventListener('pushsubscriptionchange', (event) => {
  // Browser revoked or expired subscription — user will re-subscribe on next visit
  console.log('[sw] Push subscription changed');
});
