// Browser-side push subscription management.
// Handles permission request, subscription creation, and cleanup.

const API_BASE = typeof window !== 'undefined' ? process.env.NEXT_PUBLIC_API_URL : '';

export async function subscribeToPush(): Promise<{
  status: "subscribed" | "denied" | "error";
  reason?: string;
}> {
  if (typeof window === 'undefined' || !("serviceWorker" in navigator)) {
    return { status: "error", reason: "Service Workers not supported" };
  }

  // 1. Request permission
  const permission = await Notification.requestPermission();
  if (permission === "denied") return { status: "denied" };
  if (permission !== "granted") return { status: "error", reason: "dismissed" };

  // 2. Ensure Service Worker is registered
  const registration = await navigator.serviceWorker.ready;

  // Drop any existing subscription so a key change doesn't throw InvalidStateError
  const existing = await registration.pushManager.getSubscription();
  if (existing) await existing.unsubscribe();

  // 3. Subscribe with VAPID public key
  const vapidKey = process.env.NEXT_PUBLIC_VAPID_PUBLIC_KEY;
  if (!vapidKey) return { status: "error", reason: "VAPID key not configured" };

  const subscription = await registration.pushManager.subscribe({
    userVisibleOnly: true,
    applicationServerKey: urlBase64ToUint8Array(vapidKey) as BufferSource,
  });

  // 4. Send subscription to Next.js API (which proxies to Flask/VPS)
  const resp = await fetch("/api/push/subscribe", {
    method: "POST",
    credentials: "include",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      endpoint: subscription.endpoint,
      p256dh: arrayBufferToBase64(subscription.getKey("p256dh")!),
      auth: arrayBufferToBase64(subscription.getKey("auth")!),
      browser: detectBrowser(),
    }),
  });

  if (!resp.ok) return { status: "error", reason: "server rejected" };
  return { status: "subscribed" };
}

export async function unsubscribeFromPush(): Promise<{ status: "unsubscribed" | "error" }> {
  if (typeof window === 'undefined' || !("serviceWorker" in navigator)) {
    return { status: "error" };
  }

  try {
    const registration = await navigator.serviceWorker.ready;
    const subscription = await registration.pushManager.getSubscription();

    if (subscription) {
      await fetch("/api/push/unsubscribe", {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ endpoint: subscription.endpoint }),
      });
      await subscription.unsubscribe();
    }

    return { status: "unsubscribed" };
  } catch {
    return { status: "error" };
  }
}

export async function getPushStatus(): Promise<{
  subscribed: boolean;
  permission: NotificationPermission;
}> {
  if (typeof window === 'undefined' || !("serviceWorker" in navigator)) {
    return { subscribed: false, permission: "denied" };
  }

  const permission = await Notification.permission;
  const registration = await navigator.serviceWorker.ready;
  const subscription = await registration.pushManager.getSubscription();

  return { subscribed: !!subscription, permission };
}

// ── Utilities ──

function urlBase64ToUint8Array(base64String: string): Uint8Array {
  const padding = "=".repeat((4 - (base64String.length % 4)) % 4);
  const b64 = (base64String + padding).replace(/-/g, "+").replace(/_/g, "/");
  const rawData = atob(b64);
  return new Uint8Array([...rawData].map((c) => c.charCodeAt(0)));
}

function arrayBufferToBase64(buffer: ArrayBuffer): string {
  const bytes = new Uint8Array(buffer);
  let binary = "";
  bytes.forEach((b) => (binary += String.fromCharCode(b)));
  return btoa(binary).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
}

function detectBrowser(): string {
  if (typeof navigator === 'undefined') return "unknown";
  const ua = navigator.userAgent;
  if (ua.includes("Firefox")) return "firefox";
  if (ua.includes("Edg")) return "edge";
  if (ua.includes("Chrome")) return "chrome";
  if (ua.includes("Safari")) return "safari";
  return "unknown";
}
