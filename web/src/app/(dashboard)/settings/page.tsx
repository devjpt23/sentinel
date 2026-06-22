"use client";

import { useState, useEffect } from "react";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Checkbox } from "@/components/ui/checkbox";
import { Slider } from "@/components/ui/slider";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { usePreferences, useUpdatePreferences, useUser } from "@/hooks/use-watchlist";
import { Send, CheckCircle2, XCircle, Loader2, Bot, Bell, User, Moon, Sun, LogOut, Globe, Eye, EyeOff, Lock } from "lucide-react";
import Link from "next/link";
import { subscribeToPush, unsubscribeFromPush, getPushStatus } from "@/lib/push-notifications";
import { logout } from "@/lib/auth";

// Telegram connection states
type TelegramState = "connected" | "waiting" | "not_connected";

function AuthRequired() {
  return (
    <div className="flex items-center justify-center min-h-[60vh]">
      <Card className="max-w-md">
        <CardHeader className="text-center">
          <Lock className="h-12 w-12 mx-auto mb-2 text-[#6b7f8e]" />
          <CardTitle className="text-[#f0f4f0]">Access Denied</CardTitle>
          <CardDescription>You must be signed in to manage settings.</CardDescription>
        </CardHeader>
        <CardContent className="text-center">
          <p className="text-sm text-[#6b7f8e] mb-4">Sign in or create an account to configure your settings.</p>
          <Link href="/login" className="inline-flex items-center justify-center rounded-md text-sm font-medium h-10 px-4 py-2 bg-[#84cc16] text-[#0a0e13] hover:bg-[#74b810]">
            Sign In
          </Link>
        </CardContent>
      </Card>
    </div>
  );
}

export default function SettingsPage() {
  const { data: prefs, isLoading: prefsLoading } = usePreferences();
  const { data: userData, isLoading: userLoading } = useUser();
  const updatePrefs = useUpdatePreferences();

  // Telegram state
  const [telegramState, setTelegramState] = useState<TelegramState>("not_connected");
  const [botToken, setBotToken] = useState("");
  const [showToken, setShowToken] = useState(false);
  const [testingMessage, setTestingMessage] = useState(false);

  // Form state
  const [healthChange, setHealthChange] = useState(true);
  const [verdictChange, setVerdictChange] = useState(true);
  const [riskFlagChange, setRiskFlagChange] = useState(true);
  const [zscoreZoneChange, setZscoreZoneChange] = useState(true);
  const [fscoreChange, setFscoreChange] = useState(false);
  const [checkInterval, setCheckInterval] = useState(6);
  const [healthDelta, setHealthDelta] = useState(10);

  const [theme, setTheme] = useState<"dark" | "light">("dark");

  // Push notification state
  const [pushStatus, setPushStatus] = useState<"denied" | "default" | "granted">("default");
  const [pushSubscribed, setPushSubscribed] = useState(false);
  const [pushLoading, setPushLoading] = useState(false);
  const [pushTestLoading, setPushTestLoading] = useState(false);
  const [pushError, setPushError] = useState<string | null>(null);

  // Load push status on mount
  useEffect(() => {
    if (typeof window !== "undefined") {
      getPushStatus().then((s) => {
        setPushStatus(s.permission);
        setPushSubscribed(s.subscribed);
      }).catch(() => {});
    }
  }, []);

  // Initialize Telegram state from preferences when they load
  useEffect(() => {
    if (prefs?.preferences) {
      const p = prefs.preferences as Record<string, unknown>;
      if (p.telegram_bot_token) {
        setBotToken(String(p.telegram_bot_token));
        setTelegramState(p.telegram_enabled ? "connected" : "not_connected");
      }
    }
  }, [prefs]);

  if (userLoading) {
    return <div className="flex items-center justify-center min-h-[60vh]"><Skeleton className="h-8 w-48" /></div>;
  }

  if (!userData) {
    return <AuthRequired />;
  }

  const handleSavePrefs = () => {
    updatePrefs.mutate({
      health_change: healthChange,
      verdict_change: verdictChange,
      risk_flag_change: riskFlagChange,
      zscore_zone_change: zscoreZoneChange,
      fscore_change: fscoreChange,
      check_interval_hours: checkInterval,
      health_delta_threshold: healthDelta,
    });
  };

  const handleConnectTelegram = async () => {
    if (!botToken.trim()) return;
    setTelegramState("waiting");
    try {
      const resp = await fetch("/api/user/link-telegram", {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ bot_token: botToken.trim() }),
      });
      const data = await resp.json();
      if (resp.ok && data.ok) {
        setTelegramState("connected");
      } else {
        setTelegramState("not_connected");
      }
    } catch {
      setTelegramState("not_connected");
    }
  };

  const handleDisconnectTelegram = async () => {
    setTelegramState("waiting");
    try {
      const resp = await fetch("/api/user/link-telegram", {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ bot_token: "" }),
      });
      if (resp.ok) {
        setTelegramState("not_connected");
        setBotToken("");
      } else {
        setTelegramState("connected");
      }
    } catch {
      setTelegramState("connected");
    }
  };

  // TODO: wire to a real Flask endpoint (e.g. POST /api/telegram/test-message)
  // that uses the stored bot_token to send a test message via the Telegram Bot API.
  // For now the daemon sends a welcome message when chat_id is first discovered.
  const handleTestMessage = () => {
    setTestingMessage(true);
    setTimeout(() => setTestingMessage(false), 3000);
  };

  const handleEnablePush = async () => {
    setPushLoading(true);
    setPushError(null);
    try {
      const result = await subscribeToPush();
      if (result.status === "subscribed") {
        setPushSubscribed(true);
        setPushStatus("granted");
      } else if (result.status === "denied") {
        setPushStatus("denied");
        setPushError("Browser permission denied. Enable notifications in your browser settings.");
      } else {
        setPushError(result.reason || "Failed to enable push notifications.");
      }
    } catch (e) {
      console.error("[push] subscribe failed:", e);
      setPushError("An error occurred while enabling push notifications.");
    } finally {
      setPushLoading(false);
    }
  };

  const handleDisablePush = async () => {
    setPushLoading(true);
    try {
      await unsubscribeFromPush();
      setPushSubscribed(false);
    } finally {
      setPushLoading(false);
    }
  };

  const handleTestPush = async () => {
    setPushTestLoading(true);
    try {
      const resp = await fetch("/api/push/test", {
        method: "POST",
        credentials: "include",
      });
      const data = await resp.json();
      if (!resp.ok) setPushError(data.error || "Test push failed");
    } finally {
      setPushTestLoading(false);
    }
  };

  const handleLogout = async () => {
    if ("serviceWorker" in navigator) {
      await unsubscribeFromPush().catch(() => {});
    }
    await logout();
    window.location.href = "/login";
  };

  return (
    <div className="space-y-6 max-w-3xl">
      <div>
        <h1 className="text-2xl font-bold text-[#f0f4f0]">Settings</h1>
        <p className="text-sm text-[#6b7f8e] mt-1">Manage your account, notifications, and integrations</p>
      </div>

      {/* Web Push Notifications - only for authenticated users */}
      {userData && (
      <Card>
        <CardHeader>
          <CardTitle className="text-base flex items-center gap-2">
            <Globe className="h-4 w-4" />
            Web Push Notifications
          </CardTitle>
          <CardDescription>
            Receive alerts on your device even when this site is closed
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex items-center gap-3">
            <span className="text-sm text-[#6b7f8e]">Status:</span>
            {pushSubscribed && pushStatus === "granted" && (
              <Badge variant="success" className="flex items-center gap-1">
                <CheckCircle2 className="h-3 w-3" /> Active
              </Badge>
            )}
            {pushStatus === "denied" && (
              <Badge variant="danger" className="flex items-center gap-1">
                <XCircle className="h-3 w-3" /> Blocked
              </Badge>
            )}
            {pushStatus === "default" && !pushSubscribed && (
              <Badge variant="secondary" className="flex items-center gap-1">
                Not Enabled
              </Badge>
            )}
            {pushStatus === "granted" && !pushSubscribed && (
              <Badge variant="warning" className="flex items-center gap-1">
                <Loader2 className="h-3 w-3" /> Permission granted, not subscribed
              </Badge>
            )}
          </div>

          <div className="flex gap-2 flex-wrap">
            {!pushSubscribed ? (
              <Button
                variant="primary"
                onClick={handleEnablePush}
                disabled={pushLoading || pushStatus === "denied"}
              >
                {pushLoading ? (
                  <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                ) : null}
                Enable Web Push
              </Button>
            ) : (
              <Button variant="destructive" onClick={handleDisablePush} disabled={pushLoading}>
                {pushLoading ? (
                  <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                ) : null}
                Disable Web Push
              </Button>
            )}
            {pushSubscribed && (
              <Button
                variant="outline"
                onClick={handleTestPush}
                disabled={pushTestLoading}
              >
                {pushTestLoading ? (
                  <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                ) : (
                  <Send className="h-4 w-4 mr-2" />
                )}
                Send Test Notification
              </Button>
            )}
          </div>

          {pushError && (
            <p className="text-sm text-red-400 flex items-center gap-2">
              <XCircle className="h-4 w-4" /> {pushError}
            </p>
          )}

          {pushStatus === "denied" && (
            <p className="text-xs text-[#3a5570]">
              Push notifications are blocked by your browser. Open your browser
              settings for this site and allow notifications to re-enable.
            </p>
          )}
        </CardContent>
      </Card>
      )}

      {/* Telegram Setup - only for authenticated users */}
      {userData && (
      <Card>
        <CardHeader>
          <CardTitle className="text-base flex items-center gap-2">
            <Bot className="h-4 w-4" />
            Telegram Setup
          </CardTitle>
          <CardDescription>
            Connect your Telegram bot to receive alerts and use commands
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          {/* Connection Status */}
          <div className="flex items-center gap-3">
            <span className="text-sm text-[#6b7f8e]">Status:</span>
            {telegramState === "connected" && (
              <Badge variant="success" className="flex items-center gap-1">
                <CheckCircle2 className="h-3 w-3" /> Connected
              </Badge>
            )}
            {telegramState === "waiting" && (
              <Badge variant="warning" className="flex items-center gap-1">
                <Loader2 className="h-3 w-3 animate-spin" /> Connecting...
              </Badge>
            )}
            {telegramState === "not_connected" && (
              <Badge variant="danger" className="flex items-center gap-1">
                <XCircle className="h-3 w-3" /> Not Connected
              </Badge>
            )}
          </div>

          {/* Bot Token Input */}
          <div className="space-y-2">
            <label className="text-sm text-[#6b7f8e]">Bot Token</label>
            <div className="flex gap-2">
              <Input
                type={telegramState === "connected" && !showToken ? "password" : "text"}
                placeholder="123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11"
                value={botToken}
                onChange={(e) => setBotToken(e.target.value)}
                disabled={telegramState === "connected"}
                className="flex-1"
              />
              {telegramState === "connected" && (
                <Button variant="outline" size="icon" className="shrink-0" onClick={() => setShowToken(!showToken)} title={showToken ? "Hide token" : "Show token"}>
                  {showToken ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                </Button>
              )}
            </div>
          </div>

          {/* Actions */}
          <div className="flex gap-2">
            {telegramState === "connected" ? (
              <Button variant="destructive" onClick={handleDisconnectTelegram}>
                Disconnect
              </Button>
            ) : (
              <Button variant="primary" onClick={handleConnectTelegram} disabled={!botToken.trim() || telegramState === "waiting"}>
                {telegramState === "waiting" ? (
                  <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                ) : null}
                Connect
              </Button>
            )}
            {telegramState === "connected" && (
              <Button variant="outline" onClick={handleTestMessage} disabled={testingMessage}>
                {testingMessage ? (
                  <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                ) : (
                  <Send className="h-4 w-4 mr-2" />
                )}
                Test Message
              </Button>
            )}
          </div>

          {testingMessage && (
            <p className="text-sm text-[#84cc16] flex items-center gap-2">
              <CheckCircle2 className="h-4 w-4" /> Test message sent successfully!
            </p>
          )}
        </CardContent>
      </Card>
      )}

      {/* Notification Preferences - only for authenticated users */}
      {userData && (
      <Card>
        <CardHeader>
          <CardTitle className="text-base flex items-center gap-2">
            <Bell className="h-4 w-4" />
            Notification Preferences
          </CardTitle>
          <CardDescription>
            Choose what alerts to receive and how often to check
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-6">
          {prefsLoading ? (
            <div className="space-y-4">
              {[1, 2, 3, 4, 5].map((i) => (
                <Skeleton key={i} className="h-6 w-full" />
              ))}
            </div>
          ) : (
            <>
              {/* Alert Checkboxes */}
              <div className="space-y-3">
                <p className="text-sm font-medium text-[#c8d8e4]">Alert me when...</p>
                <div className="space-y-2">
                  <label className="flex items-center gap-3 cursor-pointer">
                    <Checkbox checked={healthChange} onCheckedChange={(v) => setHealthChange(v === true)} />
                    <span className="text-sm text-[#c8d8e4]">Health score changes significantly</span>
                  </label>
                  <label className="flex items-center gap-3 cursor-pointer">
                    <Checkbox checked={verdictChange} onCheckedChange={(v) => setVerdictChange(v === true)} />
                    <span className="text-sm text-[#c8d8e4]">Verdict changes (e.g., Strong → Moderate)</span>
                  </label>
                  <label className="flex items-center gap-3 cursor-pointer">
                    <Checkbox checked={riskFlagChange} onCheckedChange={(v) => setRiskFlagChange(v === true)} />
                    <span className="text-sm text-[#c8d8e4]">New risk flags appear</span>
                  </label>
                  <label className="flex items-center gap-3 cursor-pointer">
                    <Checkbox checked={zscoreZoneChange} onCheckedChange={(v) => setZscoreZoneChange(!!v)} />
                    <span className="text-sm text-[#c8d8e4]">Z-Score zone changes (Safe → Grey → Distress)</span>
                  </label>
                  <label className="flex items-center gap-3 cursor-pointer">
                    <Checkbox checked={fscoreChange} onCheckedChange={(v) => setFscoreChange(!!v)} />
                    <span className="text-sm text-[#c8d8e4]">F-Score changes (Piotroski score)</span>
                  </label>
                </div>
              </div>

              {/* Check Interval */}
              <div>
                <Slider
                  label="Check Interval"
                  value={checkInterval}
                  min={1}
                  max={24}
                  step={1}
                  onValueChange={setCheckInterval}
                  formatValue={(v) => `${v} hour${v > 1 ? "s" : ""}`}
                />
              </div>

              {/* Health Delta Threshold */}
              <div>
                <Slider
                  label="Health Score Change Threshold"
                  value={healthDelta}
                  min={5}
                  max={50}
                  step={5}
                  onValueChange={setHealthDelta}
                  formatValue={(v) => `${v} points`}
                />
                <p className="text-xs text-[#3a5570] mt-1">
                  Only alert me if the health score changes by this many points
                </p>
              </div>

              {/* Save */}
              <Button variant="primary" onClick={handleSavePrefs} disabled={updatePrefs.isPending}>
                {updatePrefs.isPending ? (
                  <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                ) : null}
                Save Preferences
              </Button>
            </>
          )}
        </CardContent>
      </Card>
      )}

      {/* Account */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base flex items-center gap-2">
            <User className="h-4 w-4" />
            Account
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          {userLoading ? (
            <div className="space-y-3">
              <Skeleton className="h-4 w-48" />
              <Skeleton className="h-4 w-64" />
            </div>
          ) : (
            <>
              <div className="space-y-1">
                <p className="text-sm text-[#6b7f8e]">Username</p>
                <p className="text-sm text-[#f0f4f0]">{String(userData?.username ?? "user")}</p>
              </div>
              <div className="space-y-1">
                <p className="text-sm text-[#6b7f8e]">Display Name</p>
                <p className="text-sm text-[#f0f4f0]">{String(userData?.display_name ?? "—")}</p>
              </div>
              <div className="space-y-1">
                <p className="text-sm text-[#6b7f8e]">Email</p>
                <p className="text-sm text-[#f0f4f0]">{String(userData?.email ?? "—")}</p>
              </div>
              <Button variant="destructive" onClick={handleLogout}>
                <LogOut className="h-4 w-4 mr-2" />
                Sign Out
              </Button>
            </>
          )}
        </CardContent>
      </Card>

      {/* Theme Toggle */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base flex items-center gap-2">
            {theme === "dark" ? <Moon className="h-4 w-4" /> : <Sun className="h-4 w-4" />}
            Appearance
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex gap-2">
            <Button
              variant={theme === "dark" ? "primary" : "outline"}
              onClick={() => setTheme("dark")}
              className="flex items-center gap-2"
            >
              <Moon className="h-4 w-4" />
              Dark
            </Button>
            <Button
              variant={theme === "light" ? "primary" : "outline"}
              onClick={() => setTheme("light")}
              className="flex items-center gap-2"
            >
              <Sun className="h-4 w-4" />
              Light
            </Button>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}