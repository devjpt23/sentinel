// Registers the Service Worker on mount. Runs once per session.
"use client";
import { useEffect, useState } from "react";

export function PushInit() {
  const [registered, setRegistered] = useState(false);

  useEffect(() => {
    if ("serviceWorker" in navigator) {
      navigator.serviceWorker.register("/sw.js", { scope: "/" })
        .then(() => setRegistered(true))
        .catch((err) => console.warn("[push] SW registration failed:", err));
    }
  }, []);

  // No UI — silent registration
  return null;
}
