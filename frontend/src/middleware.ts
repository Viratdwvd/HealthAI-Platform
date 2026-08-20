/**
 * Next.js Edge Middleware – Route Protection
 * ------------------------------------------
 * Runs before every request. Redirects unauthenticated users to /login.
 * Public routes (login, static assets) bypass the check.
 *
 * Note: Since JWT validation in edge runtime is limited, we check for the
 * presence of the token cookie. Full JWT verification happens server-side
 * in each API route if needed.
 */

import { NextRequest, NextResponse } from "next/server";

// Routes accessible without authentication
const PUBLIC_PATHS = new Set([
  "/login",
  "/api/health",
]);

// Prefixes that are always public (static files, Next internals)
const PUBLIC_PREFIXES = ["/_next/", "/favicon", "/icons/", "/images/"];

export function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl;

  // Allow public paths
  if (PUBLIC_PATHS.has(pathname)) return NextResponse.next();
  if (PUBLIC_PREFIXES.some((p) => pathname.startsWith(p))) return NextResponse.next();

  // Check for auth token (stored in cookie by the login page)
  const token = request.cookies.get("hai_token")?.value
    ?? request.headers.get("authorization")?.replace("Bearer ", "");

  if (!token) {
    const loginUrl = new URL("/login", request.url);
    loginUrl.searchParams.set("from", pathname);
    return NextResponse.redirect(loginUrl);
  }

  return NextResponse.next();
}

export const config = {
  // Run on all routes except Next.js internals and static files
  matcher: ["/((?!_next/static|_next/image|favicon.ico).*)"],
};
