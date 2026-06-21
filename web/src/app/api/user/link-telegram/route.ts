import { NextRequest, NextResponse } from "next/server";
import { cookies } from "next/headers";

/**
 * POST /api/user/link-telegram
 *
 * Proxy route that wires the Telegram settings UI to the real Flask backend.
 *
 * Flow (matching the Streamlit version in src/display/notifications.py):
 * 1. Verify the user's session cookie to get user_id
 * 2. Save the bot_token to preferences (telegram_bot_token + telegram_enabled)
 *    - If token is empty/non-empty, telegram_enabled is toggled accordingly
 * 3. The VPS daemon periodically polls for new bot tokens and attempts
 *    chat_id discovery. Once a user messages the bot, chat_id is linked.
 */
export async function POST(request: NextRequest) {
  const cookieStore = await cookies();
  const sessionToken = cookieStore.get("session")?.value;

  if (!sessionToken) {
    return NextResponse.json({ error: "unauthorized" }, { status: 401 });
  }

  const apiUrl = process.env.NEXT_PUBLIC_API_URL;
  const apiSecretKey = process.env.API_SECRET_KEY;

  if (!apiUrl || !apiSecretKey) {
    return NextResponse.json({ error: "server misconfiguration" }, { status: 500 });
  }

  // Verify session via Flask
  const verifyResp = await fetch(`${apiUrl}/api/auth/token/verify`, {
    method: "POST",
    headers: { "Content-Type": "application/json", "X-API-Key": apiSecretKey },
    body: JSON.stringify({ session_token: sessionToken }),
  });

  if (!verifyResp.ok) {
    return NextResponse.json({ error: "unauthorized" }, { status: 401 });
  }

  const verifyData = await verifyResp.json();
  const userId = verifyData.user?.id;
  if (!userId) {
    return NextResponse.json({ error: "unauthorized" }, { status: 401 });
  }

  // Parse request body
  const body = await request.json();
  const botToken = body.bot_token ?? "";

  // Save (or clear) the bot token in preferences
  const resp = await fetch(`${apiUrl}/api/preferences/${userId}`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "X-API-Key": apiSecretKey,
    },
    body: JSON.stringify({
      telegram_bot_token: botToken,
      telegram_enabled: botToken !== "",
    }),
  });

  const data = await resp.json();
  return NextResponse.json(data, { status: resp.status });
}
