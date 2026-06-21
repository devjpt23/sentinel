import Link from "next/link";
import { cookies } from "next/headers";
import { redirect } from "next/navigation";
import { TickerSearch } from "@/components/TickerSearch";
import { TopMovers } from "@/components/TopMovers";
import { SESSION_COOKIE_NAME } from "@/lib/constants";
import {
  LayoutDashboard, ListTodo, Search as SearchIcon, BarChart3,
  FileText, Bell, ShieldAlert, Settings, TrendingUp, Shield, DollarSign,
} from "lucide-react";

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
            Find any stock, instantly
          </h1>
          <p className="text-sm text-[#6b7f8e] mb-8">
            Health scores, fair value, and risk alerts — all in plain English.
          </p>
          <TickerSearch />
        </div>

        {/* Top Movers */}
        <TopMovers />

        {/* Navigation tabs */}
        <div className="mt-12 border-t border-[#1e2d3a] pt-8">
          <p className="text-xs text-[#6b7f8e] text-center mb-4">Explore Sentinel</p>
          <div className="grid grid-cols-3 sm:grid-cols-5 gap-3">
            <NavItem href="/" icon={LayoutDashboard} label="Dashboard" />
            <NavItem href="/watchlist" icon={ListTodo} label="Watchlist" />
            <NavItem href="/screener" icon={SearchIcon} label="Screener" />
            <NavItem href="/sectors" icon={BarChart3} label="Sectors" />
            <NavItem href="/sec-filings" icon={FileText} label="SEC Filings" />
            <NavItem href="/notifications" icon={Bell} label="Notifications" />
            <NavItem href="/alerts" icon={ShieldAlert} label="Alerts" />
            <NavItem href="/settings" icon={Settings} label="Settings" />
          </div>
        </div>

        {/* Feature pills */}
        <div className="flex flex-wrap justify-center gap-3 mt-8">
          <span className="inline-flex items-center gap-1.5 rounded-full border border-[#1e2d3a] bg-[#111b26] px-3 py-1.5 text-xs text-[#6b7f8e]">
            <Shield className="h-3 w-3 text-[#84cc16]" /> Health Score
          </span>
          <span className="inline-flex items-center gap-1.5 rounded-full border border-[#1e2d3a] bg-[#111b26] px-3 py-1.5 text-xs text-[#6b7f8e]">
            <DollarSign className="h-3 w-3 text-[#84cc16]" /> Fair Value (DCF)
          </span>
          <span className="inline-flex items-center gap-1.5 rounded-full border border-[#1e2d3a] bg-[#111b26] px-3 py-1.5 text-xs text-[#6b7f8e]">
            <TrendingUp className="h-3 w-3 text-[#84cc16]" /> Risk Alerts
          </span>
        </div>

        {/* Footer */}
        <p className="mt-12 text-center text-[11px] text-[#3a5570]">
          Sentinel — Built for traders who want clarity, not complexity.
        </p>
      </div>
    </div>
  );
}

function NavItem({ href, icon: Icon, label }: { href: string; icon: any; label: string }) {
  return (
    <Link
      href={href}
      className="flex flex-col items-center gap-2 rounded-xl border border-[#1e2d3a] bg-[#111b26] p-4 text-[#6b7f8e] hover:border-[#84cc16]/40 hover:text-[#84cc16] hover:bg-[#111b26]/80 transition-all"
    >
      <Icon className="h-5 w-5" />
      <span className="text-xs font-medium">{label}</span>
    </Link>
  );
}