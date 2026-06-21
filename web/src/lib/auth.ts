"use server";

import { cookies } from "next/headers";
import { API_BASE_URL, SESSION_COOKIE_NAME, SESSION_MAX_AGE } from "./constants";
interface UserSummary {
  id: string;
  email: string;
  name: string;
}

/**
 * Get the current session token from cookies (server-side).
 */
export async function getSessionToken(): Promise<string | null> {
  const cookieStore = await cookies();
  return cookieStore.get(SESSION_COOKIE_NAME)?.value ?? null;
}

/**
 * Set the session token as an httpOnly cookie.
 */
export async function setSessionToken(token: string): Promise<void> {
  const cookieStore = await cookies();
  cookieStore.set(SESSION_COOKIE_NAME, token, {
    httpOnly: true,
    secure: process.env.NODE_ENV === "production",
    sameSite: "lax",
    maxAge: SESSION_MAX_AGE,
    path: "/",
  });
}

/**
 * Clear the session cookie (logout).
 */
export async function clearSession(): Promise<void> {
  const cookieStore = await cookies();
  cookieStore.delete(SESSION_COOKIE_NAME);
}

/**
 * Validate a session token against the Flask API.
 * Returns the user if valid, null otherwise.
 */
export async function validateSession(): Promise<UserSummary | null> {
  const token = await getSessionToken();
  if (!token) return null;

  try {
    const res = await fetch(`${API_BASE_URL}/api/auth/me`, {
      method: "GET",
      headers: {
        "Content-Type": "application/json",
        "X-Session-Token": token,
      },
      cache: "no-store",
    });

    if (!res.ok) return null;

    const data = await res.json();
    return data.user || null;
  } catch {
    return null;
  }
}

/**
 * Login via email/password through the Flask API.
 */
export async function login(
  username: string,
  password: string
): Promise<{ success: boolean; error?: string; user?: UserSummary }> {
  try {
    const res = await fetch(`${API_BASE_URL}/api/user/login`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-API-Key": process.env.API_SECRET_KEY || "",
      },
      body: JSON.stringify({ username, password }),
    });

    if (!res.ok) {
      const data = await res.json().catch(() => null);
      return { success: false, error: data?.error || "Login failed" };
    }

    const data = await res.json();
    // Flask returns: { user: {...}, session_token: "..." }
    if (data.session_token) {
      await setSessionToken(data.session_token);
      return {
        success: true,
        user: {
          id: String(data.user?.id ?? ""),
          email: data.user?.email ?? "",
          name: data.user?.display_name ?? data.user?.username ?? "",
        },
      };
    }

    return { success: false, error: "Invalid response from server" };
  } catch {
    return { success: false, error: "Network error" };
  }
}

/**
 * Register a new user via the Flask API.
 */
export async function register(
  username: string,
  password: string,
  displayName?: string
): Promise<{ success: boolean; error?: string; user?: UserSummary }> {
  try {
    const res = await fetch(`${API_BASE_URL}/api/user/register`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-API-Key": process.env.API_SECRET_KEY || "",
      },
      body: JSON.stringify({ username, password, display_name: displayName }),
    });

    if (!res.ok) {
      const data = await res.json().catch(() => null);
      if (res.status === 409) {
        return { success: false, error: "Username already taken" };
      }
      return { success: false, error: data?.error || "Registration failed" };
    }

    const data = await res.json();
    if (data.session_token) {
      await setSessionToken(data.session_token);
      return {
        success: true,
        user: {
          id: String(data.user?.id ?? ""),
          email: data.user?.email ?? "",
          name: data.user?.display_name ?? data.user?.username ?? "",
        },
      };
    }

    return { success: false, error: "Invalid response from server" };
  } catch {
    return { success: false, error: "Network error" };
  }
}

/**
 * Request a password reset email.
 */
export async function requestPasswordReset(
  email: string
): Promise<{ success: boolean; error?: string }> {
  try {
    const res = await fetch(`${API_BASE_URL}/api/auth/password-reset/request`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-API-Key": process.env.API_SECRET_KEY || "",
      },
      body: JSON.stringify({ email }),
    });

    if (!res.ok) {
      const data = await res.json().catch(() => null);
      return { success: false, error: data?.error || "Failed to request password reset" };
    }

    return { success: true };
  } catch {
    return { success: false, error: "Network error" };
  }
}

/**
 * Confirm password reset with token.
 */
export async function confirmPasswordReset(
  token: string,
  newPassword: string
): Promise<{ success: boolean; error?: string }> {
  try {
    const res = await fetch(`${API_BASE_URL}/api/auth/password-reset/confirm`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-API-Key": process.env.API_SECRET_KEY || "",
      },
      body: JSON.stringify({ token, new_password: newPassword }),
    });

    if (!res.ok) {
      const data = await res.json().catch(() => null);
      return { success: false, error: data?.error || "Failed to reset password" };
    }

    return { success: true };
  } catch {
    return { success: false, error: "Network error" };
  }
}

/**
 * Logout — clear session and revoke token on the API.
 */
export async function logout(): Promise<void> {
  const token = await getSessionToken();
  if (token) {
    try {
      await fetch(`${API_BASE_URL}/api/auth/token`, {
        method: "DELETE",
        headers: { "X-Session-Token": token },
      });
    } catch {
      // Ignore — clear local session anyway
    }
  }
  await clearSession();
}
