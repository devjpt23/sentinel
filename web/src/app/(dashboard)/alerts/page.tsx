"use client";

import { useState, useMemo, useEffect } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  Plus, Trash2, ToggleLeft, ToggleRight, AlertTriangle, Info,
  AlertCircle, ChevronDown, ChevronRight, Lock, Globe, Bot, Bell,
  CheckCircle2, XCircle, Loader2, Send, Settings,
} from "lucide-react";
import { api } from "@/lib/api-client";
import type { AlertRule, AlertCondition } from "@/types/api";
import { useAlertBuilder } from "@/stores/alert-builder-store";
import { useUser, usePreferences, useUpdatePreferences } from "@/hooks/use-watchlist";
import { getPushStatus } from "@/lib/push-notifications";
import { SIGNAL_CATALOG, SIGNAL_CATEGORIES, SIGNAL_CATALOG_BY_CATEGORY, getSignalById } from "@/lib/signal-catalog";
import QuickAlerts from "@/components/alerts/QuickAlerts";
import type { AlertTemplate } from "@/components/alerts/QuickAlerts";
import Link from "next/link";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Checkbox } from "@/components/ui/checkbox";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Card, CardContent, CardHeader, CardTitle, CardDescription, CardFooter } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { Separator } from "@/components/ui/separator";
import { toast } from "sonner";

const OPERATORS = [">", "<", ">=", "<=", "==", "crosses_above", "crosses_below", "touches_upper", "touches_lower"];

function severityIcon(severity: string) {
  switch (severity) {
    case "info": return <Info className="h-4 w-4 text-[#84cc16]" />;
    case "warning": return <AlertTriangle className="h-4 w-4 text-yellow-400" />;
    case "critical": return <AlertCircle className="h-4 w-4 text-red-400" />;
  }
}

function severityBadgeClass(severity: string) {
  switch (severity) {
    case "info": return "border-[#84cc16]/30 bg-[#84cc16]/20 text-[#84cc16]";
    case "warning": return "border-yellow-500/30 bg-yellow-500/20 text-yellow-400";
    case "critical": return "border-red-500/30 bg-red-500/20 text-red-400";
  }
}

function AuthRequired() {
  return (
    <div className="flex items-center justify-center min-h-[60vh]">
      <Card className="max-w-md">
        <CardHeader className="text-center">
          <Lock className="h-12 w-12 mx-auto mb-2 text-[#6b7f8e]" />
          <CardTitle className="text-[#f0f4f0]">Access Denied</CardTitle>
          <CardDescription>You must be signed in to manage alert rules.</CardDescription>
        </CardHeader>
        <CardContent className="text-center">
          <p className="text-sm text-[#6b7f8e] mb-4">Sign in or create an account to create and manage alerts.</p>
          <Link href="/login" className="inline-flex items-center justify-center rounded-md text-sm font-medium h-10 px-4 py-2 bg-[#84cc16] text-[#0a0e13] hover:bg-[#74b810]">
            Sign In
          </Link>
        </CardContent>
      </Card>
    </div>
  );
}

function DeliveryChannels({ userId }: { userId: number }) {
  const [pushStatus, setPushStatus] = useState<"denied" | "default" | "granted">("default");
  const [pushSubscribed, setPushSubscribed] = useState(false);
  const { data: prefs } = usePreferences(userId);

  useEffect(() => {
    getPushStatus().then((s) => {
      setPushStatus(s.permission);
      setPushSubscribed(s.subscribed);
    }).catch(() => {});
  }, []);

  const tgConnected = !!(prefs?.preferences as Record<string, unknown>)?.telegram_enabled;

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="text-sm flex items-center gap-2">
            <Globe className="h-4 w-4" />
            Web Push
          </CardTitle>
        </CardHeader>
        <CardContent className="pt-0">
          <div className="flex items-center justify-between">
            <span className="text-xs text-[#6b7f8e]">
              {pushSubscribed ? "Receiving alerts" : "Not configured"}
            </span>
            {pushSubscribed ? (
              <Badge variant="success" className="text-xs">
                <CheckCircle2 className="h-3 w-3 mr-1" /> Active
              </Badge>
            ) : (
              <Badge variant="secondary" className="text-xs">Inactive</Badge>
            )}
          </div>
          <Link
            href="/settings"
            className="text-xs text-[#84cc16] hover:underline mt-2 inline-block"
          >
            Configure in Settings
          </Link>
        </CardContent>
      </Card>

      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="text-sm flex items-center gap-2">
            <Bot className="h-4 w-4" />
            Telegram
          </CardTitle>
        </CardHeader>
        <CardContent className="pt-0">
          <div className="flex items-center justify-between">
            <span className="text-xs text-[#6b7f8e]">
              {tgConnected ? "Connected" : "Not connected"}
            </span>
            {tgConnected ? (
              <Badge variant="success" className="text-xs">
                <CheckCircle2 className="h-3 w-3 mr-1" /> Active
              </Badge>
            ) : (
              <Badge variant="secondary" className="text-xs">Inactive</Badge>
            )}
          </div>
          <Link
            href="/settings"
            className="text-xs text-[#84cc16] hover:underline mt-2 inline-block"
          >
            Configure in Settings
          </Link>
        </CardContent>
      </Card>
    </div>
  );
}

function RulesList({ userId }: { userId: number }) {
  const queryClient = useQueryClient();

  const { data, isLoading } = useQuery({
    queryKey: ["alerts", userId],
    queryFn: () => api.get<{ rules: AlertRule[] }>(`/api/alerts/${userId}`),
  });

  const rules = (data?.rules ?? []) as AlertRule[];

  const toggleMutation = useMutation({
    mutationFn: (ruleId: string) =>
      api.post<{ ok: boolean }>(`/api/alerts/${userId}/${ruleId}/toggle`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["alerts"] });
      toast.success("Rule updated");
    },
  });

  const deleteMutation = useMutation({
    mutationFn: (ruleId: string) =>
      api.delete<{ ok: boolean }>(`/api/alerts/${userId}/${ruleId}`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["alerts"] });
      toast.success("Rule deleted");
    },
  });

  if (isLoading) {
    return (
      <div className="space-y-4">
        {Array.from({ length: 2 }).map((_, i) => (
          <Skeleton key={i} className="h-28 w-full" />
        ))}
      </div>
    );
  }

  if (rules.length === 0) {
    return (
      <div className="text-center py-8 text-[#6b7f8e]">
        <AlertTriangle className="h-8 w-8 mx-auto mb-2 opacity-50" />
        <p className="text-sm">No alert rules yet</p>
        <p className="text-xs">Use the quick templates above or create a custom rule below</p>
      </div>
    );
  }

  return (
    <div className="space-y-3">
      {rules.map((rule) => (
        <Card key={rule.id}>
          <CardHeader className="pb-3">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                {severityIcon(rule.severity)}
                <CardTitle className="text-[#f0f4f0] text-sm">{rule.name}</CardTitle>
                <Badge variant="outline" className={severityBadgeClass(rule.severity)}>{rule.severity}</Badge>
              </div>
              <div className="flex items-center gap-2">
                <button onClick={() => toggleMutation.mutate(rule.id)} className="text-[#6b7f8e] hover:text-[#f0f4f0] transition-colors">
                  {rule.enabled ? <ToggleRight className="h-5 w-5 text-[#84cc16]" /> : <ToggleLeft className="h-5 w-5 text-[#3a5570]" />}
                </button>
                <Button variant="ghost" size="icon" className="h-7 w-7 text-[#6b7f8e] hover:text-red-400" onClick={() => deleteMutation.mutate(rule.id)}>
                  <Trash2 className="h-4 w-4" />
                </Button>
              </div>
            </div>
            <CardDescription className="text-xs">
              {rule.scope === "watchlist" ? "Watchlist-wide" : rule.ticker} &middot; {rule.conditions.length} condition{rule.conditions.length > 1 ? "s" : ""} &middot; Logic: {rule.logic}
            </CardDescription>
          </CardHeader>
          <CardContent className="pt-0">
            <div className="flex flex-wrap gap-2">
              {rule.conditions.map((c, i) => (
                <div key={i} className="rounded-md bg-[#1a2a38]/50 px-3 py-1.5 text-xs text-[#6b7f8e]">
                  {c.signal_id} {c.operator} {c.value}
                  {c.days ? ` (${c.days}d)` : ""}
                  {c.period ? ` (${c.period})` : ""}
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      ))}
    </div>
  );
}

function CustomRuleBuilder({ userId, onCreated }: { userId: number; onCreated: () => void }) {
  const queryClient = useQueryClient();
  const {
    name, severity, scope, ticker, conditions, logic,
    setName, setSeverity, setScope, setTicker,
    addCondition, updateCondition, removeCondition, setLogic, reset,
  } = useAlertBuilder();

  const createMutation = useMutation({
    mutationFn: () => {
      const finalName = name.trim() || autoGenerateName();
      const body = {
        name: finalName,
        severity,
        scope,
        ...(scope === "single" ? { ticker } : {}),
        conditions: conditions.filter((c) => c.signal_id),
        logic,
      };
      return api.post<{ ok: boolean; rule_id?: string }>(`/api/alerts/${userId}`, body);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["alerts"] });
      reset();
      onCreated();
      toast.success("Alert rule created");
    },
  });

  function autoGenerateName() {
    const parts = conditions.filter((c) => c.signal_id).map((c) => {
      const sig = getSignalById(c.signal_id);
      return sig ? `${sig.name} ${c.operator} ${c.value}` : `${c.signal_id} ${c.operator} ${c.value}`;
    });
    if (parts.length === 0) return "Untitled Rule";
    if (parts.length === 1) return parts[0];
    return parts.join(` ${logic} `);
  }

  return (
    <div className="space-y-5">
      {/* Rule Name */}
      <div>
        <Label>Rule Name</Label>
        <Input
          placeholder={autoGenerateName()}
          value={name}
          onChange={(e) => setName(e.target.value)}
        />
        <p className="text-xs text-[#3a5570] mt-1">Leave blank to auto-generate from conditions</p>
      </div>

      {/* Severity + Scope row */}
      <div className="grid grid-cols-2 gap-4">
        <div>
          <Label>Severity</Label>
          <div className="flex gap-2 mt-1">
            {(["info", "warning", "critical"] as const).map((s) => (
              <Button
                key={s}
                variant={severity === s ? "default" : "outline"}
                size="sm"
                onClick={() => setSeverity(s)}
                className={severity === s ? "" : "text-[#6b7f8e]"}
              >
                {s.charAt(0).toUpperCase() + s.slice(1)}
              </Button>
            ))}
          </div>
        </div>
        <div>
          <Label>Scope</Label>
          <div className="flex gap-2 mt-1">
            <Button variant={scope === "watchlist" ? "default" : "outline"} size="sm" onClick={() => setScope("watchlist")}>Watchlist</Button>
            <Button variant={scope === "single" ? "default" : "outline"} size="sm" onClick={() => setScope("single")}>Single Ticker</Button>
          </div>
        </div>
      </div>

      {scope === "single" && (
        <div>
          <Label>Ticker</Label>
          <Input placeholder="e.g. AAPL" value={ticker} onChange={(e) => setTicker(e.target.value.toUpperCase())} />
        </div>
      )}

      {/* Conditions */}
      <div>
        <Label className="mb-3 block">When...</Label>
        {conditions.map((cond, idx) => {
          const categorySignals = SIGNAL_CATALOG_BY_CATEGORY[cond.signal_category] ?? [];
          const selectedSignal = cond.signal_id ? getSignalById(cond.signal_id) : null;

          return (
            <div key={idx} className="space-y-3 mb-4 rounded-lg border border-[#1e2d3a] p-4">
              <div className="flex items-center justify-between">
                <span className="text-sm text-[#6b7f8e]">Condition {idx + 1}</span>
                {conditions.length > 1 && (
                  <Button variant="ghost" size="sm" className="h-6 w-6 p-0 text-[#6b7f8e]" onClick={() => removeCondition(idx)}>
                    <Trash2 className="h-3.5 w-3.5" />
                  </Button>
                )}
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <Label className="text-xs text-[#6b7f8e]">Category</Label>
                  <Select value={cond.signal_category} onValueChange={(v) => updateCondition(idx, "signal_category", v)}>
                    <SelectTrigger><SelectValue placeholder="Select" /></SelectTrigger>
                    <SelectContent>
                      {SIGNAL_CATEGORIES.map((c) => <SelectItem key={c} value={c}>{c}</SelectItem>)}
                    </SelectContent>
                  </Select>
                </div>
                <div>
                  <Label className="text-xs text-[#6b7f8e]">Signal</Label>
                  <Select value={cond.signal_id} onValueChange={(v) => updateCondition(idx, "signal_id", v)}>
                    <SelectTrigger><SelectValue placeholder="Select" /></SelectTrigger>
                    <SelectContent>
                      {categorySignals.map((s) => (
                        <SelectItem key={s.id} value={s.id}>
                          <span>{s.name}</span>
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                  {selectedSignal && (
                    <p className="text-xs text-[#3a5570] mt-1">{selectedSignal.description}</p>
                  )}
                </div>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <Label className="text-xs text-[#6b7f8e]">Operator</Label>
                  <Select value={cond.operator} onValueChange={(v) => updateCondition(idx, "operator", v)}>
                    <SelectTrigger><SelectValue placeholder="Select" /></SelectTrigger>
                    <SelectContent>
                      {selectedSignal
                        ? selectedSignal.operators.map((o) => <SelectItem key={o} value={o}>{o}</SelectItem>)
                        : OPERATORS.map((o) => <SelectItem key={o} value={o}>{o}</SelectItem>)
                      }
                    </SelectContent>
                  </Select>
                </div>
                <div>
                  <Label className="text-xs text-[#6b7f8e]">Value</Label>
                  <Input type="number" value={cond.value || ""} onChange={(e) => updateCondition(idx, "value", parseFloat(e.target.value) || 0)} />
                </div>
              </div>

              {selectedSignal?.requires_days && (
                <div>
                  <Label className="text-xs text-[#6b7f8e]">Days Lookback</Label>
                  <Input type="number" value={cond.days || ""} onChange={(e) => updateCondition(idx, "days", parseInt(e.target.value) || 0)} />
                </div>
              )}

              {selectedSignal?.requires_period && (
                <div>
                  <Label className="text-xs text-[#6b7f8e]">Period</Label>
                  <Select value={cond.period || ""} onValueChange={(v) => updateCondition(idx, "period", v)}>
                    <SelectTrigger><SelectValue placeholder="Select period" /></SelectTrigger>
                    <SelectContent>
                      {["1D", "1W", "1M", "3M", "6M", "1Y"].map((p) => <SelectItem key={p} value={p}>{p}</SelectItem>)}
                    </SelectContent>
                  </Select>
                </div>
              )}
            </div>
          );
        })}

        {conditions.length < 3 && (
          <Button variant="outline" size="sm" onClick={addCondition}>
            <Plus className="h-4 w-4 mr-1" /> Add Condition
          </Button>
        )}
      </div>

      {/* Logic operator between conditions */}
      {conditions.length > 1 && (
        <div>
          <Label>Condition Logic</Label>
          <div className="flex gap-2 mt-1">
            <Button variant={logic === "AND" ? "default" : "outline"} size="sm" onClick={() => setLogic("AND")}>AND (all must match)</Button>
            <Button variant={logic === "OR" ? "default" : "outline"} size="sm" onClick={() => setLogic("OR")}>OR (any can match)</Button>
          </div>
        </div>
      )}

      <Separator />

      <Button variant="primary" onClick={() => createMutation.mutate()} disabled={createMutation.isPending || !conditions[0]?.signal_id}>
        {createMutation.isPending ? <Loader2 className="h-4 w-4 mr-1 animate-spin" /> : <Plus className="h-4 w-4 mr-1" />}
        Save Rule
      </Button>
    </div>
  );
}

function PreferencesSection({ userId }: { userId: number }) {
  const { data: prefs, isLoading: prefsLoading } = usePreferences(userId);
  const updatePrefs = useUpdatePreferences(userId);

  const [healthChange, setHealthChange] = useState(true);
  const [verdictChange, setVerdictChange] = useState(true);
  const [riskFlagChange, setRiskFlagChange] = useState(true);
  const [zscoreZoneChange, setZscoreZoneChange] = useState(true);
  const [fscoreChange, setFscoreChange] = useState(false);
  const [checkInterval, setCheckInterval] = useState(6);
  const [healthDelta, setHealthDelta] = useState(10);

  useEffect(() => {
    if (prefs?.preferences) {
      const p = prefs.preferences as Record<string, unknown>;
      if (typeof p.health_change === "boolean") setHealthChange(p.health_change);
      if (typeof p.verdict_change === "boolean") setVerdictChange(p.verdict_change);
      if (typeof p.risk_flag_change === "boolean") setRiskFlagChange(p.risk_flag_change);
      if (typeof p.zscore_zone_change === "boolean") setZscoreZoneChange(p.zscore_zone_change);
      if (typeof p.fscore_change === "boolean") setFscoreChange(p.fscore_change);
      if (typeof p.check_interval_hours === "number") setCheckInterval(p.check_interval_hours);
      if (typeof p.health_delta_threshold === "number") setHealthDelta(p.health_delta_threshold);
    }
  }, [prefs]);

  const [showPrefs, setShowPrefs] = useState(false);

  const handleSave = () => {
    updatePrefs.mutate({
      health_change: healthChange,
      verdict_change: verdictChange,
      risk_flag_change: riskFlagChange,
      zscore_zone_change: zscoreZoneChange,
      fscore_change: fscoreChange,
      check_interval_hours: checkInterval,
      health_delta_threshold: healthDelta,
    }, {
      onSuccess: () => toast.success("Preferences saved"),
    });
  };

  return (
    <Card>
      <CardHeader className="pb-3 cursor-pointer" onClick={() => setShowPrefs(!showPrefs)}>
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Bell className="h-4 w-4" />
            <CardTitle className="text-sm">Notification Preferences</CardTitle>
          </div>
          {showPrefs ? <ChevronDown className="h-4 w-4" /> : <ChevronRight className="h-4 w-4" />}
        </div>
        <CardDescription>Built-in alerts for health, risk, and score changes</CardDescription>
      </CardHeader>
      {showPrefs && (
        <CardContent className="space-y-5 pt-0">
          {prefsLoading ? (
            <div className="space-y-3">
              {[1, 2, 3, 4, 5].map((i) => (
                <Skeleton key={i} className="h-6 w-full" />
              ))}
            </div>
          ) : (
            <>
              <div className="space-y-2">
                <label className="flex items-center gap-3 cursor-pointer">
                  <Checkbox checked={healthChange} onCheckedChange={(v) => setHealthChange(v === true)} />
                  <span className="text-sm text-[#c8d8e4]">Health score changes significantly</span>
                </label>
                <label className="flex items-center gap-3 cursor-pointer">
                  <Checkbox checked={verdictChange} onCheckedChange={(v) => setVerdictChange(v === true)} />
                  <span className="text-sm text-[#c8d8e4]">Verdict changes (e.g., Strong &rarr; Moderate)</span>
                </label>
                <label className="flex items-center gap-3 cursor-pointer">
                  <Checkbox checked={riskFlagChange} onCheckedChange={(v) => setRiskFlagChange(v === true)} />
                  <span className="text-sm text-[#c8d8e4]">New risk flags appear</span>
                </label>
                <label className="flex items-center gap-3 cursor-pointer">
                  <Checkbox checked={zscoreZoneChange} onCheckedChange={(v) => setZscoreZoneChange(!!v)} />
                  <span className="text-sm text-[#c8d8e4]">Z-Score zone changes (Safe &#8594; Grey &#8594; Distress)</span>
                </label>
                <label className="flex items-center gap-3 cursor-pointer">
                  <Checkbox checked={fscoreChange} onCheckedChange={(v) => setFscoreChange(!!v)} />
                  <span className="text-sm text-[#c8d8e4]">F-Score changes (Piotroski score)</span>
                </label>
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div>
                  <Label className="text-xs text-[#6b7f8e]">Check Interval</Label>
                  <Select value={String(checkInterval)} onValueChange={(v) => setCheckInterval(Number(v))}>
                    <SelectTrigger className="mt-1"><SelectValue /></SelectTrigger>
                    <SelectContent>
                      {[1, 2, 3, 6, 12, 24].map((h) => (
                        <SelectItem key={h} value={String(h)}>Every {h} hour{h > 1 ? "s" : ""}</SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
                <div>
                  <Label className="text-xs text-[#6b7f8e]">Health Delta Threshold</Label>
                  <Select value={String(healthDelta)} onValueChange={(v) => setHealthDelta(Number(v))}>
                    <SelectTrigger className="mt-1"><SelectValue /></SelectTrigger>
                    <SelectContent>
                      {[5, 10, 15, 20, 25, 30].map((d) => (
                        <SelectItem key={d} value={String(d)}>{d} points</SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
              </div>

              <Button
                variant="primary"
                size="sm"
                onClick={handleSave}
                disabled={updatePrefs.isPending}
              >
                {updatePrefs.isPending ? <Loader2 className="h-4 w-4 mr-1 animate-spin" /> : null}
                Save Preferences
              </Button>
            </>
          )}
        </CardContent>
      )}
    </Card>
  );
}

function AlertsPageFallback() {
  return (
    <div className="space-y-6 max-w-4xl">
      <div>
        <h2 className="text-2xl font-bold text-[#f0f4f0]">Notification Settings</h2>
        <p className="text-[#6b7f8e] mt-1">Manage alerts, delivery channels, and notification preferences</p>
      </div>
      <Card>
        <CardContent className="py-12 text-center">
          <AlertTriangle className="h-10 w-10 mx-auto mb-3 text-yellow-400" />
          <p className="text-[#c8d8e4] font-medium">Unable to load alerts</p>
          <p className="text-sm text-[#6b7f8e] mt-1 mb-4">The alert service is temporarily unavailable. Your rules are still active and will continue to fire.</p>
          <Button variant="outline" onClick={() => window.location.reload()}>Retry</Button>
        </CardContent>
      </Card>
    </div>
  );
}

export default function AlertsPage() {
  const { data: userData, isLoading: userLoading } = useUser();
  const [showBuilder, setShowBuilder] = useState(false);
  const queryClient = useQueryClient();

  if (userLoading) {
    return <div className="flex items-center justify-center min-h-[60vh]"><Skeleton className="h-8 w-48" /></div>;
  }

  if (!userData) {
    return <AuthRequired />;
  }

  const userId = userData.id;

  const handleQuickAdd = (template: AlertTemplate) => {
    const body = {
      name: template.name,
      severity: template.severity,
      scope: template.scope,
      ...(template.ticker ? { ticker: template.ticker } : {}),
      conditions: template.conditions,
      logic: template.logic,
    };
    api.post<{ ok: boolean }>(`/api/alerts/${userId}`, body).then(() => {
      queryClient.invalidateQueries({ queryKey: ["alerts"] });
      toast.success(`"${template.name}" alert created`);
    }).catch(() => {
      toast.error("Failed to create alert");
    });
  };

  return (
    <div className="space-y-6 max-w-4xl">
      <div>
        <h2 className="text-2xl font-bold text-[#f0f4f0]">Notification Settings</h2>
        <p className="text-[#6b7f8e] mt-1">Manage alerts, delivery channels, and notification preferences in one place</p>
      </div>

      {/* Delivery Channels */}
      <div>
        <h3 className="text-sm font-semibold text-[#c8d8e4] mb-3">Delivery Channels</h3>
        <DeliveryChannels userId={userId} />
      </div>

      <Separator />

      {/* Quick Alert Templates */}
      <div>
        <h3 className="text-sm font-semibold text-[#c8d8e4] mb-3">Quick Alerts</h3>
        <p className="text-xs text-[#6b7f8e] mb-4">One-click presets for common trading alerts</p>
        <QuickAlerts onAdd={handleQuickAdd} />
      </div>

      <Separator />

      {/* Your Rules */}
      <div>
        <div className="flex items-center justify-between mb-3">
          <h3 className="text-sm font-semibold text-[#c8d8e4]">Your Alert Rules</h3>
          <Button variant="outline" size="sm" onClick={() => setShowBuilder(!showBuilder)}>
            <Plus className="h-4 w-4 mr-1" />
            {showBuilder ? "Close" : "Create Custom Rule"}
          </Button>
        </div>
        <RulesList userId={userId} />
      </div>

      {/* Custom Rule Builder */}
      {showBuilder && (
        <Card>
          <CardHeader>
            <CardTitle className="text-sm">Custom Rule Builder</CardTitle>
            <CardDescription>Create a custom alert rule with your own conditions</CardDescription>
          </CardHeader>
          <CardContent>
            <CustomRuleBuilder userId={userId} onCreated={() => setShowBuilder(false)} />
          </CardContent>
        </Card>
      )}

      <Separator />

      {/* Notification Preferences */}
      <PreferencesSection userId={userId} />
    </div>
  );
}
