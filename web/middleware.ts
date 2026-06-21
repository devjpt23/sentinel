import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";
import { SESSION_COOKIE_NAME } from "./src/lib/constants";

// Routes that require authentication
const PROTECTED_PATHS = ["/dashboard", "/watchlist", "/sectors", "/screener", "/sec-filings", "/notifications", "/alerts", "/settings", "/admin", "/company"];
const PUBLIC_PATHS = ["/login", "/oauth/callback", "/about"];

export function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl;
  const sessionToken = request.cookies.get(SESSION_COOKIE_NAME)?.value;

  // Check if the path requires auth
  const isProtected = PROTECTED_PATHS.some(
    (p) => pathname === p || pathname.startsWith(`${p}/`)
  );

  if (isProtected && !sessionToken) {
    // Redirect to login with return URL
    const loginUrl = new URL("/login", request.url);
    loginUrl.searchParams.set("callbackUrl", pathname);
    return NextResponse.redirect(loginUrl);
  }

  // If already logged in and trying to access login, redirect to dashboard
  if (pathname === "/login" && sessionToken) {
    return NextResponse.redirect(new URL("/", request.url));
  }

  return NextResponse.next();
}

export const config = {
  matcher: [
    /*
     * Match all request paths except:
     * - api routes (handled by Next.js)
     * - static files (_next/static, _next/image, favicon.ico)
     * - public folder
     */
    "/((?!_next/static|_next/image|favicon.ico|.*\\.(?:svg|png|jpg|jpeg|gif|webp)$).*)",
  ],
};
