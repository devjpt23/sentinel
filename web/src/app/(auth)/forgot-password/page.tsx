"use client";

import { useState } from "react";
import Link from "next/link";
import { Shield, Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { requestPasswordReset } from "@/lib/auth";

export default function ForgotPasswordPage() {
  const [email, setEmail] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [submitted, setSubmitted] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError("");
    const result = await requestPasswordReset(email);
    if (result.success) {
      setSubmitted(true);
    } else {
      setError(result.error || "Failed to request password reset");
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-[#0a0e13] px-4">
      <div className="absolute inset-0 bg-gradient-to-br from-[#84cc16]/5 via-transparent to-[#84cc16]/5 pointer-events-none" />

      <div className="w-full max-w-md space-y-8 relative">
        <div className="flex flex-col items-center gap-4">
          <div className="flex items-center gap-2">
            <div className="h-10 w-10 rounded-xl bg-[#84cc16] flex items-center justify-center shadow-lg shadow-[#84cc16]/20">
              <Shield className="h-6 w-6 text-[#0a0e13]" />
            </div>
            <span className="text-2xl font-bold text-[#f0f4f0]">Sentinel</span>
          </div>
          <p className="text-[#6b7f8e] text-center">
            {submitted ? "Check your email" : "Enter your email and we'll send you a reset link"}
          </p>
        </div>

        <div className="rounded-xl border border-[#1e2d3a] bg-[#111922] p-6 space-y-4 shadow-xl">
          {submitted ? (
            <div className="space-y-4 text-center">
              <p className="text-[#f0f4f0]">
                We sent a password reset link to{" "}
                <span className="text-[#84cc16] font-medium">{email}</span>
              </p>
              <p className="text-sm text-[#6b7f8e]">
                Didn&apos;t receive the email? Check your spam folder or try again.
              </p>
              <Button variant="outline" className="w-full" onClick={() => { setSubmitted(false); setEmail(""); }}>
                Try another email
              </Button>
            </div>
          ) : (
            <form onSubmit={handleSubmit} className="space-y-4">
              <div className="space-y-2">
                <Label htmlFor="email">Email</Label>
                <Input
                  id="email"
                  type="email"
                  placeholder="you@example.com"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  required
                  disabled={loading}
                />
              </div>
              {error && <p className="text-sm text-red-400">{error}</p>}
              <Button variant="primary" type="submit" className="w-full" disabled={loading}>
                {loading ? (
                  <><Loader2 className="mr-2 h-4 w-4 animate-spin" />Sending...</>
                ) : (
                  "Send reset link"
                )}
              </Button>
            </form>
          )}
        </div>

        <p className="text-center text-sm text-[#6b7f8e]">
          Remember your password?{" "}
          <Link href="/login" className="text-[#84cc16] hover:text-[#65a30d] transition-colors">
            Sign in
          </Link>
        </p>
      </div>
    </div>
  );
}
