"use client";

import { useState } from "react";
import { Sidebar } from "@/components/layout/sidebar";
import { TopNav } from "@/components/layout/top-nav";
import { MarqueeTicker } from "@/components/layout/marquee";
import { RightPanel } from "@/components/layout/right-panel";

export default function DashboardLayout({ children }: { children: React.ReactNode }) {
  const [rightPanelOpen, setRightPanelOpen] = useState(false);
  const [sidebarOpen, setSidebarOpen] = useState(false);

  return (
    <div className="min-h-screen bg-[#0a0e13]" suppressHydrationWarning>
      {/* Mobile sidebar overlay */}
      {sidebarOpen && (
        <div className="fixed inset-0 z-40 bg-black/50 md:hidden" onClick={() => setSidebarOpen(false)} />
      )}
      <Sidebar mobileOpen={sidebarOpen} onMobileClose={() => setSidebarOpen(false)} />
      <div className="ml-0 md:ml-52 flex flex-col">
        <TopNav onToggleRightPanel={() => setRightPanelOpen((o) => !o)} onToggleSidebar={() => setSidebarOpen((o) => !o)} />
        <MarqueeTicker />
        <main className="flex-1 p-4 md:p-6">
          {children}
        </main>
      </div>
      {rightPanelOpen && <RightPanel />}
    </div>
  );
}
