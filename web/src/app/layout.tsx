import type { Metadata } from "next";
import "./globals.css";
import { Providers } from "./providers";
import { PushInit } from "@/components/push-init";

export const metadata: Metadata = {
  title: "Sentinel — Financial Analysis Dashboard",
  description: "Professional-grade stock analysis, health scoring, and portfolio monitoring",
  manifest: "/manifest.json",
  appleWebApp: {
    capable: true,
    title: "Sentinel",
    statusBarStyle: "default",
  },
  icons: {
    apple: "/icon-192.png",
  },
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body className="bg-[#0a0e13] text-[#f0f4f0] antialiased" suppressHydrationWarning>
        <Providers>{children}</Providers>
        <PushInit />
      </body>
    </html>
  );
}
