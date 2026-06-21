import { NextRequest, NextResponse } from "next/server";
import { cookies } from "next/headers";

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

  // Parse subscription data
  const body = await request.json();
  const { endpoint, p256dh, auth, browser } = body;

  if (!endpoint || !p256dh || !auth) {
    return NextResponse.json({ error: "endpoint, p256dh, and auth are required" }, { status: 400 });
  }

  // Forward to Flask push subscribe endpoint
  const resp = await fetch(`${apiUrl}/api/push/subscribe`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "X-API-Key": apiSecretKey,
      "X-Session-Token": sessionToken,
    },
    body: JSON.stringify({ user_id: userId, endpoint, p256dh, auth, browser }),
  });

  const data = await resp.json();
  return NextResponse.json(data, { status: resp.status });
}
