import { NextRequest, NextResponse } from "next/server";
import { cookies } from "next/headers";

const cache = new Map<string, { data: unknown; ts: number }>();
const CACHE_TTL = 30_000; // 30 seconds

export async function GET(_request: NextRequest) {
  const cookieStore = await cookies();
  const sessionToken = cookieStore.get("session")?.value;

  if (!sessionToken) {
    return NextResponse.json({ error: "no session" }, { status: 401 });
  }

  // Return cached response for this token if still fresh
  const cached = cache.get(sessionToken);
  if (cached && Date.now() - cached.ts < CACHE_TTL) {
    return NextResponse.json(cached.data, { status: 200 });
  }

  const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:5252";

  try {
    const resp = await fetch(`${apiUrl}/api/auth/me`, {
      method: "GET",
      headers: {
        "X-Session-Token": sessionToken,
      },
    });

    const data = await resp.json();

    if (resp.ok) {
      cache.set(sessionToken, { data, ts: Date.now() });
    }

    return NextResponse.json(data, { status: resp.status });
  } catch (err) {
    const message =
      err instanceof Error ? err.message : "failed to fetch auth status";
    return NextResponse.json({ error: message }, { status: 502 });
  }
}
