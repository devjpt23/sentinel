"use client";

import { Suspense, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import Link from "next/link";
import { Shield, Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { login } from "@/lib/auth";

function LoginForm() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const callbackUrl = searchParams.get("callbackUrl") || "/watchlist";

  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError("");
    const result = await login(username, password);
    if (result.success) {
      router.push(callbackUrl);
    } else {
      setError(result.error || "Login failed");
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-[#0a0e13] px-4">
      {/* Subtle gradient background */}
      <div className="absolute inset-0 bg-gradient-to-br from-[#84cc16]/5 via-transparent to-[#84cc16]/5 pointer-events-none" />

      <div className="w-full max-w-md space-y-8 relative">
        <div className="flex flex-col items-center gap-4">
          <div className="flex items-center gap-2">
            <div className="h-10 w-10 rounded-xl bg-[#84cc16] flex items-center justify-center shadow-lg shadow-[#84cc16]/20">
              <Shield className="h-6 w-6 text-[#0a0e13]" />
            </div>
            <span className="text-2xl font-bold text-[#f0f4f0]">Sentinel</span>
          </div>
          <p className="text-[#6b7f8e] text-center">Sign in to access your financial dashboard</p>
        </div>
        <div className="rounded-xl border border-[#1e2d3a] bg-[#111922] p-6 space-y-4 shadow-xl">
          <form onSubmit={handleSubmit} className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="username">Username</Label>
              <Input id="username" type="text" placeholder="your_username" value={username} onChange={(e) => setUsername(e.target.value)} required disabled={loading} />
            </div>
            <div className="space-y-2">
              <Label htmlFor="password">Password</Label>
              <Input id="password" type="password" placeholder="..." value={password} onChange={(e) => setPassword(e.target.value)} required disabled={loading} />
            </div>
            {error && <p className="text-sm text-red-400">{error}</p>}
            <Button variant="primary" type="submit" className="w-full" disabled={loading}>
              {loading ? (<><Loader2 className="mr-2 h-4 w-4 animate-spin" />Signing in...</>) : "Sign In"}
            </Button>
            <div className="text-right">
              <Link href="/forgot-password" className="text-sm text-[#84cc16] hover:text-[#65a30d] transition-colors">
                Forgot password?
              </Link>
            </div>
          </form>
        </div>
        <p className="text-center text-sm text-[#6b7f8e]">Don&apos;t have an account? <Link href="/register" className="text-[#84cc16] hover:text-[#65a30d] transition-colors">Create an account</Link></p>
      </div>
    </div>
  );
}

export default function LoginPage() {
  return (
    <Suspense fallback={<div className="min-h-screen flex items-center justify-center bg-[#0a0e13]"><div className="text-[#6b7f8e]">Loading...</div></div>}>
      <LoginForm />
    </Suspense>
  );
}
