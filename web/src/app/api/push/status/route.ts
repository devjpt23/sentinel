import { NextRequest, NextResponse } from "next/server";
import { cookies } from "next/headers";

export async function GET(request: NextRequest) {
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

  // Verify session first
  const verifyResp = await fetch(`${apiUrl}/api/auth/token/verify`, {
    method: "POST",
    headers: { "Content-Type": "application/json", "X-API-Key": apiSecretKey },
    body: JSON.stringify({ session_token: sessionToken }),
  });

  if (!verifyResp.ok) {
    return NextResponse.json({ error: "unauthorized" }, { status: 401 });
  }

  const verifyData = await verifyResp.json();
  if (!verifyData.user?.id) {
    return NextResponse.json({ error: "unauthorized" }, { status: 401 });
  }

  const resp = await fetch(`${apiUrl}/api/push/status`, {
    method: "GET",
    headers: {
      "X-API-Key": apiSecretKey,
      "X-Session-Token": sessionToken,
    },
  });

  const data = await resp.json();
  return NextResponse.json(data, { status: resp.status });
}
