"use client";

import { Suspense, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import Link from "next/link";
import { Shield, Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { confirmPasswordReset } from "@/lib/auth";

function ResetPasswordForm() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const token = searchParams.get("token");

  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState(false);

  if (!token) {
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
          </div>
          <div className="rounded-xl border border-[#1e2d3a] bg-[#111922] p-6 space-y-4 shadow-xl text-center">
            <p className="text-red-400">Invalid reset link</p>
            <p className="text-sm text-[#6b7f8e]">
              Please request a new password reset from the login page.
            </p>
            <Link href="/login">
              <Button variant="primary" className="w-full">Back to login</Button>
            </Link>
          </div>
        </div>
      </div>
    );
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");

    if (newPassword.length < 6) {
      setError("Password must be at least 6 characters");
      return;
    }

    if (newPassword !== confirmPassword) {
      setError("Passwords do not match");
      return;
    }

    setLoading(true);
    const result = await confirmPasswordReset(token, newPassword);
    if (result.success) {
      setSuccess(true);
    } else {
      setError(result.error || "Failed to reset password");
      setLoading(false);
    }
  };

  if (success) {
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
          </div>
          <div className="rounded-xl border border-[#1e2d3a] bg-[#111922] p-6 space-y-4 shadow-xl text-center">
            <p className="text-[#f0f4f0] text-lg font-medium">Password updated</p>
            <p className="text-sm text-[#6b7f8e]">
              Your password has been reset successfully. You can now sign in.
            </p>
            <Link href="/login">
              <Button variant="primary" className="w-full">Sign in</Button>
            </Link>
          </div>
        </div>
      </div>
    );
  }

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
          <p className="text-[#6b7f8e] text-center">Set a new password</p>
        </div>

        <div className="rounded-xl border border-[#1e2d3a] bg-[#111922] p-6 space-y-4 shadow-xl">
          <form onSubmit={handleSubmit} className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="newPassword">New password</Label>
              <Input
                id="newPassword"
                type="password"
                placeholder="At least 6 characters"
                value={newPassword}
                onChange={(e) => setNewPassword(e.target.value)}
                required
                disabled={loading}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="confirmPassword">Confirm password</Label>
              <Input
                id="confirmPassword"
                type="password"
                placeholder="Re-enter your new password"
                value={confirmPassword}
                onChange={(e) => setConfirmPassword(e.target.value)}
                required
                disabled={loading}
              />
            </div>
            {error && <p className="text-sm text-red-400">{error}</p>}
            <Button variant="primary" type="submit" className="w-full" disabled={loading}>
              {loading ? (
                <><Loader2 className="mr-2 h-4 w-4 animate-spin" />Resetting...</>
              ) : (
                "Reset password"
              )}
            </Button>
          </form>
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

export default function ResetPasswordPage() {
  return (
    <Suspense fallback={<div className="min-h-screen flex items-center justify-center bg-[#0a0e13]"><div className="text-[#6b7f8e]">Loading...</div></div>}>
      <ResetPasswordForm />
    </Suspense>
  );
}
