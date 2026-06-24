"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { startTransition, useState } from "react";
import { cn } from "@/lib/utils";
import { api } from "@/lib/api-client";
import { useQuery } from "@tanstack/react-query";
import { logout } from "@/lib/auth";
import {
  LayoutDashboard,
  ListTodo,
  Bell,
  ShieldAlert,
  Search,
  BarChart3,
  FileText,
  Settings,
  Users,
  Info,
  LogOut,
  Network,
} from "lucide-react";

const dashboardItems = [
  { href: "/", label: "Dashboard", icon: LayoutDashboard },
  { href: "/watchlist", label: "Watchlist", icon: ListTodo },
  { href: "/screener", label: "Screener", icon: Search },
  { href: "/sectors", label: "Sectors", icon: BarChart3 },
  { href: "/sec-filings", label: "SEC Filings", icon: FileText },
];

const settingsItems = [
  { href: "/notifications", label: "Notifications", icon: Bell },
  { href: "/alerts", label: "Alerts", icon: ShieldAlert },
  { href: "/settings", label: "Settings", icon: Settings },
  { href: "/admin", label: "Admin", icon: Users },
  { href: "/about", label: "About", icon: Info },
];

function SidebarUser() {
  const { data } = useQuery({
    queryKey: ["user", "me"],
    queryFn: () => api.getMe() as Promise<{ username?: string; email?: string }>,
    retry: false,
    staleTime: Infinity,
    refetchOnWindowFocus: false,
  });
  const router = useRouter();
  const name = data?.username ?? "Guest";
  const initial = name.charAt(0).toUpperCase();
  const handleSignOut = () => {
    startTransition(async () => {
      await logout();
      router.push("/login");
      router.refresh();
    });
  };

  return (
    <div className="flex items-center gap-3 px-4 py-3">
      <div className="h-8 w-8 rounded-full bg-[#84cc16] flex items-center justify-center text-[#0a0e13] font-bold text-sm">
        {initial}
      </div>
      <div className="flex-1 min-w-0">
        <p className="text-sm font-medium text-[#f0f4f0] truncate">{name}</p>
        <p className="text-xs text-[#6b7f8e] truncate">{data?.email ?? ""}</p>
      </div>
      {data?.username && (
        <button onClick={handleSignOut} className="text-[#6b7f8e] hover:text-red-400 transition-colors p-1" title="Sign out">
          <LogOut className="h-4 w-4" />
        </button>
      )}
    </div>
  );
}

function SidebarSearch() {
  const router = useRouter();
  const [query, setQuery] = useState("");

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const ticker = query.trim().toUpperCase();
    if (ticker) {
      router.push(`/company/${ticker}`);
      setQuery("");
    }
  };

  const goSupplyChain = () => {
    const ticker = query.trim().toUpperCase();
    if (ticker) {
      router.push(`/supply-chain/${ticker}`);
      setQuery("");
    }
  };

  return (
    <div className="px-3 pb-2">
      <form onSubmit={handleSubmit} className="relative mb-1.5">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-[#6b7f8e]" />
        <input
          type="text"
          placeholder="Search ticker..."
          value={query}
          onChange={(e) => setQuery(e.target.value.toUpperCase())}
          className="w-full h-8 rounded-md border border-[#1e2d3a] bg-[#1a2a38]/50 pl-9 pr-3 text-xs text-[#f0f4f0] placeholder:text-[#6b7f8e] focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-[#84cc16]/50"
        />
      </form>
      {query && (
        <button
          onClick={goSupplyChain}
          className="w-full flex items-center gap-2 px-2 py-1.5 rounded-md text-xs text-[#6b7f8e] hover:bg-[#1a2a38] hover:text-[#84cc16] transition-colors"
        >
          <Network className="h-3 w-3" />
          Supply Chain: {query}
        </button>
      )}
    </div>
  );
}

function SectionLabel({ children }: { children: React.ReactNode }) {
  return (
    <p className="px-4 pt-4 pb-1 text-[10px] font-semibold uppercase tracking-wider text-[#3a5570]">
      {children}
    </p>
  );
}

function NavItem({ item, active, onClick }: { item: (typeof dashboardItems)[0]; active: boolean; onClick?: () => void }) {
  return (
    <Link
      href={item.href}
      prefetch={false}
      replace
      onClick={(e) => {
        onClick?.();
        // Use direct navigation to avoid client-side router hangs
        e.preventDefault();
        window.location.href = item.href;
      }}
      className={cn(
        "flex items-center gap-3 mx-2 px-3 py-2 rounded-lg text-sm transition-all duration-150",
        active
          ? "bg-[#84cc16] text-[#0a0e13] font-semibold"
          : "text-[#6b7f8e] hover:bg-[#1a2a38] hover:text-[#c8d8e4]"
      )}
    >
      <item.icon className="h-4 w-4 shrink-0" />
      <span className="truncate">{item.label}</span>
    </Link>
  );
}

export function Sidebar({ mobileOpen, onMobileClose }: { mobileOpen?: boolean; onMobileClose?: () => void } = {}) {
  const pathname = usePathname();

  return (
    <aside className={cn(
      "fixed left-0 top-0 z-50 flex h-screen w-52 flex-col border-r border-[#1e2d3a] bg-[#0d1319] transition-transform duration-200",
      "md:z-30 md:translate-x-0",
      mobileOpen ? "translate-x-0" : "-translate-x-full md:translate-x-0"
    )}>
      {/* User Profile */}
      <SidebarUser />

      {/* Search */}
      <SidebarSearch />

      {/* Nav */}
      <nav className="flex-1 overflow-y-auto pb-4">
        <SectionLabel>Dashboards</SectionLabel>
        {dashboardItems.map((item) => (
          <NavItem key={item.href} item={item} active={pathname === item.href} onClick={onMobileClose} />
        ))}

        <SectionLabel>System</SectionLabel>
        {settingsItems.map((item) => (
          <NavItem key={item.href} item={item} active={pathname === item.href} onClick={onMobileClose} />
        ))}
      </nav>

      {/* Branding */}
      <div className="flex items-center gap-2 px-4 py-3 border-t border-[#1e2d3a]">
        <div className="h-6 w-6 rounded bg-[#84cc16] flex items-center justify-center">
          <span className="text-[#0a0e13] font-bold text-xs">S</span>
        </div>
        <span className="text-sm font-semibold text-[#6b7f8e]">Sentinel</span>
      </div>
    </aside>
  );
}
