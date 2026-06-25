import Link from "next/link";
import { cookies } from "next/headers";
import { redirect } from "next/navigation";
import { TickerSearch } from "@/components/TickerSearch";
import { TopMovers } from "@/components/TopMovers";
import { SESSION_COOKIE_NAME } from "@/lib/constants";

export default async function LandingPage() {
  const cookieStore = await cookies();
  const sessionCookie = cookieStore.get(SESSION_COOKIE_NAME);

  if (sessionCookie) {
    redirect("/watchlist");
  }
  return (
    <div className="min-h-screen bg-[#0a0e13] flex flex-col relative overflow-hidden">
      {/* Ambient gradient */}
      <div className="absolute inset-0 bg-gradient-to-br from-[#84cc16]/8 via-transparent to-[#84cc16]/5 pointer-events-none" />

      {/* Nav */}
      <header className="flex items-center justify-between px-6 py-4 border-b border-[#1e2d3a] relative">
        <div className="flex items-center gap-2">
          <div className="flex h-7 w-7 items-center justify-center rounded-md bg-[#84cc16] text-xs font-bold text-[#0a0e13]">S</div>
          <span className="text-sm font-semibold text-[#f0f4f0]">Sentinel</span>
        </div>
        <Link
          href="/login"
          className="text-xs text-[#6b7f8e] hover:text-[#84cc16] transition-colors"
        >
          Sign In
        </Link>
      </header>

      {/* Main content */}
      <div className="mx-auto max-w-4xl px-6 py-10 relative">
        {/* Hero + Search */}
        <div className="text-center mb-10">
          <h1 className="text-3xl font-bold text-[#f0f4f0] mb-2">
            Sentinel — Stock Analysis That Works For You
          </h1>
          <p className="text-sm text-[#6b7f8e] mb-8">
            Health scores, fair value, and risk alerts — all in plain English.
          </p>
          <TickerSearch />
        </div>

        {/* Top Movers */}
        <TopMovers />
      </div>
    </div>
  );
}