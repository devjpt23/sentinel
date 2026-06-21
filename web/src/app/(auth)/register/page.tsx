"use client";

import { Suspense, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { Shield, Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { register } from "@/lib/auth";

function RegisterForm() {
  const router = useRouter();

  const [username, setUsername] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError("");

    if (!username.trim()) {
      setError("Username is required");
      setLoading(false);
      return;
    }

    if (password.length < 4) {
      setError("Password must be at least 4 characters");
      setLoading(false);
      return;
    }

    if (password !== confirmPassword) {
      setError("Passwords do not match");
      setLoading(false);
      return;
    }

    const result = await register(username, password, displayName || undefined);
    if (result.success) {
      router.push("/watchlist");
    } else {
      setError(result.error || "Registration failed");
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
          <p className="text-[#6b7f8e] text-center">Create your account to get started</p>
        </div>
        <div className="rounded-xl border border-[#1e2d3a] bg-[#111922] p-6 space-y-4 shadow-xl">
          <form onSubmit={handleSubmit} className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="username">Username</Label>
              <Input id="username" type="text" placeholder="your_username" value={username} onChange={(e) => setUsername(e.target.value)} required disabled={loading} />
            </div>
            <div className="space-y-2">
              <Label htmlFor="displayName">Display Name (optional)</Label>
              <Input id="displayName" type="text" placeholder="Your Name" value={displayName} onChange={(e) => setDisplayName(e.target.value)} disabled={loading} />
            </div>
            <div className="space-y-2">
              <Label htmlFor="password">Password</Label>
              <Input id="password" type="password" placeholder="Min 4 characters" value={password} onChange={(e) => setPassword(e.target.value)} required disabled={loading} />
            </div>
            <div className="space-y-2">
              <Label htmlFor="confirmPassword">Confirm Password</Label>
              <Input id="confirmPassword" type="password" placeholder="Re-enter password" value={confirmPassword} onChange={(e) => setConfirmPassword(e.target.value)} required disabled={loading} />
            </div>
            {error && <p className="text-sm text-red-400">{error}</p>}
            <Button variant="primary" type="submit" className="w-full" disabled={loading}>
              {loading ? (<><Loader2 className="mr-2 h-4 w-4 animate-spin" />Creating account...</>) : "Create Account"}
            </Button>
          </form>
        </div>
        <p className="text-center text-sm text-[#6b7f8e]">Already have an account? <Link href="/login" className="text-[#84cc16] hover:text-[#65a30d] transition-colors">Sign in</Link></p>
      </div>
    </div>
  );
}

export default function RegisterPage() {
  return (
    <Suspense fallback={<div className="min-h-screen flex items-center justify-center bg-[#0a0e13]"><div className="text-[#6b7f8e]">Loading...</div></div>}>
      <RegisterForm />
    </Suspense>
  );
}
