"use client";

import { useState } from "react";
import { usePathname } from "next/navigation";
import Link from "next/link";
import { Bell, Settings, ChevronRight, PanelRight, Menu } from "lucide-react";

const breadcrumbMap: Record<string, { label: string; parent?: { label: string; href: string } }> = {
  "/": { label: "Overview", parent: { label: "Dashboards", href: "/" } },
  "/watchlist": { label: "Watchlist", parent: { label: "Dashboards", href: "/" } },
  "/screener": { label: "Screener", parent: { label: "Dashboards", href: "/" } },
  "/sectors": { label: "Sectors", parent: { label: "Dashboards", href: "/" } },
  "/sec-filings": { label: "SEC Filings", parent: { label: "Dashboards", href: "/" } },
  "/notifications": { label: "Notifications", parent: { label: "Settings", href: "/settings" } },
  "/alerts": { label: "Alerts", parent: { label: "Settings", href: "/settings" } },
  "/settings": { label: "Settings", parent: { label: "Settings", href: "/settings" } },
  "/admin": { label: "Admin", parent: { label: "Settings", href: "/settings" } },
  "/about": { label: "About", parent: { label: "Settings", href: "/settings" } },
};

function resolveBreadcrumb(pathname: string): { label: string; parent?: { label: string; href: string } } {
  if (breadcrumbMap[pathname]) return breadcrumbMap[pathname];

  // Dynamic route patterns
  const companyMatch = pathname.match(/^\/company\/([^/]+)/);
  if (companyMatch) return { label: companyMatch[1].toUpperCase(), parent: { label: "Dashboards", href: "/" } };

  const supplyChainMatch = pathname.match(/^\/supply-chain\/([^/]+)/);
  if (supplyChainMatch) return { label: `${supplyChainMatch[1].toUpperCase()} Supply Chain`, parent: { label: "Dashboards", href: "/" } };

  return { label: "Page" };
}

export function TopNav({ onToggleRightPanel, onToggleSidebar }: { onToggleRightPanel: () => void; onToggleSidebar?: () => void }) {
  const pathname = usePathname();
  const bc = resolveBreadcrumb(pathname);

  return (
    <header className="sticky top-0 z-40 flex h-14 items-center justify-between border-b border-[#1e2d3a] bg-[#0a0e13]/80 px-4 md:px-6 backdrop-blur-sm">
      {/* Hamburger (mobile only) */}
      <button onClick={onToggleSidebar} className="md:hidden rounded-lg p-2 text-[#6b7f8e] hover:text-[#f0f4f0] hover:bg-[#1a2a38] transition-colors mr-1" aria-label="Open menu">
        <Menu className="h-5 w-5" />
      </button>
      {/* Breadcrumb + Title */}
      <div>
        <div className="flex items-center gap-1 text-xs text-[#6b7f8e]">
          {bc.parent && (
            <>
              <Link href={bc.parent.href} className="hover:text-[#c8d8e4] transition-colors">
                {bc.parent.label}
              </Link>
              <ChevronRight className="h-3 w-3" />
            </>
          )}
          <span className="text-[#c8d8e4]">{bc.label}</span>
        </div>
        <h1 className="text-lg font-semibold text-[#f0f4f0] leading-tight">{bc.label}</h1>
      </div>

      {/* Action Icons */}
      <div className="flex items-center gap-1">
        <Link
          href="/notifications"
          className="rounded-lg p-2 text-[#6b7f8e] hover:text-[#f0f4f0] hover:bg-[#1a2a38] transition-colors"
          title="Notifications"
        >
          <Bell className="h-4 w-4" />
        </Link>
        <Link
          href="/settings"
          className="rounded-lg p-2 text-[#6b7f8e] hover:text-[#f0f4f0] hover:bg-[#1a2a38] transition-colors"
          title="Settings"
        >
          <Settings className="h-4 w-4" />
        </Link>
        <button
          onClick={onToggleRightPanel}
          className="rounded-lg p-2 text-[#6b7f8e] hover:text-[#f0f4f0] hover:bg-[#1a2a38] transition-colors"
          title="Toggle panel"
        >
          <PanelRight className="h-4 w-4" />
        </button>
      </div>
    </header>
  );
}
