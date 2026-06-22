import { NextRequest, NextResponse } from "next/server";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:5252";
const API_KEY = process.env.API_SECRET_KEY || "";

export async function GET(request: NextRequest) {
  return proxy(request, "GET");
}

export async function POST(request: NextRequest) {
  return proxy(request, "POST");
}

export async function PUT(request: NextRequest) {
  return proxy(request, "PUT");
}

export async function DELETE(request: NextRequest) {
  return proxy(request, "DELETE");
}

async function proxy(request: NextRequest, _method: string) {
  const path = request.nextUrl.pathname;
  const search = request.nextUrl.search;

  try {
    const headers: Record<string, string> = {
      "Content-Type": "application/json",
    };
    if (API_KEY) {
      headers["X-API-Key"] = API_KEY;
    }

    const sessionToken = request.cookies.get("session")?.value;
    if (sessionToken) {
      headers["X-Session-Token"] = sessionToken;
    }

    let body: BodyInit | null = null;
    if (request.method !== "GET" && request.method !== "HEAD") {
      body = await request.text();
    }

    const resp = await fetch(`${API_BASE}${path}${search}`, {
      method: request.method,
      headers,
      body,
    });

    const data = await resp.json();
    return NextResponse.json(data, { status: resp.status });
  } catch (err) {
    const message =
      err instanceof Error ? err.message : "proxy error";
    return NextResponse.json({ error: message }, { status: 502 });
  }
}
