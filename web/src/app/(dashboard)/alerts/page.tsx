"use client";

import { useState, useMemo } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Plus, Trash2, ToggleLeft, ToggleRight, AlertTriangle, Info, AlertCircle, ChevronDown, Lock } from "lucide-react";
import { api } from "@/lib/api-client";
import type { AlertRule, AlertCondition, SignalEntry } from "@/types/api";
import { useAlertBuilder } from "@/stores/alert-builder-store";
import { useUser } from "@/hooks/use-watchlist";
import Link from "next/link";
import { Tabs } from "@/components/ui/tabs";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Switch } from "@/components/ui/switch";
import { Card, CardContent, CardHeader, CardTitle, CardDescription, CardFooter } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { Separator } from "@/components/ui/separator";
import { toast } from "sonner";

const MOCK_USER_ID = 1;

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

function MyRulesTab() {
  const queryClient = useQueryClient();

  const { data, isLoading } = useQuery({
    queryKey: ["alerts", MOCK_USER_ID],
    queryFn: () => api.get<{ rules: AlertRule[] }>(`/api/alerts/${MOCK_USER_ID}`),
  });

  const rules = (data?.rules ?? []) as AlertRule[];

  const toggleMutation = useMutation({
    mutationFn: (ruleId: string) =>
      api.post<{ ok: boolean }>(`/api/alerts/${MOCK_USER_ID}/${ruleId}/toggle`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["alerts"] });
      toast.success("Rule updated");
    },
  });

  const deleteMutation = useMutation({
    mutationFn: (ruleId: string) =>
      api.delete<{ ok: boolean }>(`/api/alerts/${MOCK_USER_ID}/${ruleId}`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["alerts"] });
      toast.success("Rule deleted");
    },
  });

  if (isLoading) {
    return (
      <div className="space-y-4">
        {Array.from({ length: 3 }).map((_, i) => (
          <Skeleton key={i} className="h-32 w-full" />
        ))}
      </div>
    );
  }

  if (rules.length === 0) {
    return (
      <div className="text-center py-12 text-[#6b7f8e]">
        <AlertTriangle className="h-12 w-12 mx-auto mb-3 opacity-50" />
        <p className="text-lg">No alert rules yet</p>
        <p className="text-sm">Create your first rule in the Create Rule tab</p>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {rules.map((rule) => (
        <Card key={rule.id}>
          <CardHeader className="pb-3">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                {severityIcon(rule.severity)}
                <CardTitle className="text-[#f0f4f0]">{rule.name}</CardTitle>
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
            <CardDescription>
              {rule.scope === "watchlist" ? "Watchlist-wide" : rule.ticker} &middot; {rule.conditions.length} condition{rule.conditions.length > 1 ? "s" : ""} &middot; Logic: {rule.logic}
            </CardDescription>
          </CardHeader>
          <CardContent className="pt-0">
            <div className="flex flex-wrap gap-2">
              {rule.conditions.map((c, i) => (
                <div key={i} className="rounded-md bg-[#1a2a38]/50 px-3 py-1.5 text-xs text-[#6b7f8e]">
                  {c.signal} {c.operator} {c.value}
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

function CreateRuleTab() {
  const queryClient = useQueryClient();
  const {
    name, severity, scope, ticker, conditions, logic,
    setName, setSeverity, setScope, setTicker,
    addCondition, updateCondition, removeCondition, setLogic, reset,
  } = useAlertBuilder();

  const { data: signalsData } = useQuery({
    queryKey: ["alert-signals"],
    queryFn: () => api.get<{ signals: SignalEntry[] }>("/api/alerts/signals"),
  });

  const signals = (signalsData?.signals ?? []) as SignalEntry[];

  const categories = useMemo(() => [...new Set(signals.map((s) => s.category))], [signals]);

  const signalsByCategory = useMemo(() => {
    const map: Record<string, SignalEntry[]> = {};
    for (const s of signals) {
      if (!map[s.category]) map[s.category] = [];
      map[s.category].push(s);
    }
    return map;
  }, [signals]);

  const createMutation = useMutation({
    mutationFn: () => {
      const body = {
        name,
        severity,
        scope,
        ...(scope === "single" ? { ticker } : {}),
        conditions: conditions.filter((c) => c.signal),
        logic,
      };
      return api.post<{ ok: boolean; rule_id?: string }>(`/api/alerts/${MOCK_USER_ID}`, body);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["alerts"] });
      reset();
      toast.success("Alert rule created");
    },
  });

  return (
    <div className="max-w-2xl space-y-6">
      {/* Rule Name */}
      <div>
        <Label>Rule Name</Label>
        <Input placeholder="e.g. Tech stocks price drop alert" value={name} onChange={(e) => setName(e.target.value)} />
      </div>

      {/* Severity */}
      <div>
        <Label>Severity</Label>
        <Select value={severity} onValueChange={(v) => setSeverity(v as "info" | "warning" | "critical")}>
          <SelectTrigger>
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="info">Info</SelectItem>
            <SelectItem value="warning">Warning</SelectItem>
            <SelectItem value="critical">Critical</SelectItem>
          </SelectContent>
        </Select>
      </div>

      {/* Scope */}
      <div>
        <Label>Scope</Label>
        <Select value={scope} onValueChange={(v) => setScope(v as "watchlist" | "single")}>
          <SelectTrigger>
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="watchlist">Watchlist-wide</SelectItem>
            <SelectItem value="single">Single Ticker</SelectItem>
          </SelectContent>
        </Select>
      </div>

      {scope === "single" && (
        <div>
          <Label>Ticker</Label>
          <Input placeholder="e.g. AAPL" value={ticker} onChange={(e) => setTicker(e.target.value.toUpperCase())} />
        </div>
      )}

      {/* Conditions */}
      <div>
        <Label className="mb-3 block">Conditions (up to 3)</Label>
        {conditions.map((cond, idx) => {
          const categorySignals = signalsByCategory[cond.signal_category] ?? [];
          const selectedSignal = signals.find((s) => s.id === cond.signal || s.name === cond.signal);

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
                      {categories.map((c) => <SelectItem key={c} value={c}>{c}</SelectItem>)}
                    </SelectContent>
                  </Select>
                </div>
                <div>
                  <Label className="text-xs text-[#6b7f8e]">Signal</Label>
                  <Select value={cond.signal} onValueChange={(v) => updateCondition(idx, "signal", v)}>
                    <SelectTrigger><SelectValue placeholder="Select" /></SelectTrigger>
                    <SelectContent>
                      {categorySignals.map((s) => <SelectItem key={s.id} value={s.id}>{s.name}</SelectItem>)}
                    </SelectContent>
                  </Select>
                </div>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <Label className="text-xs text-[#6b7f8e]">Operator</Label>
                  <Select value={cond.operator} onValueChange={(v) => updateCondition(idx, "operator", v)}>
                    <SelectTrigger><SelectValue placeholder="Select" /></SelectTrigger>
                    <SelectContent>
                      {OPERATORS.map((o) => <SelectItem key={o} value={o}>{o}</SelectItem>)}
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
          <Label>Logic Between Conditions</Label>
          <div className="flex gap-2 mt-2">
            <Button variant={logic === "AND" ? "default" : "outline"} size="sm" onClick={() => setLogic("AND")}>AND</Button>
            <Button variant={logic === "OR" ? "default" : "outline"} size="sm" onClick={() => setLogic("OR")}>OR</Button>
          </div>
        </div>
      )}

      <Separator />

      <Button variant="primary" onClick={() => createMutation.mutate()} disabled={createMutation.isPending || !name || !conditions[0]?.signal}>
        <Plus className="h-4 w-4 mr-1" />
        Save Rule
      </Button>
    </div>
  );
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

export default function AlertsPage() {
  const [activeTab, setActiveTab] = useState("rules");
  const { data: userData, isLoading: userLoading } = useUser();

  if (userLoading) {
    return <div className="flex items-center justify-center min-h-[60vh]"><Skeleton className="h-8 w-48" /></div>;
  }

  if (!userData) {
    return <AuthRequired />;
  }

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-bold text-[#f0f4f0]">Custom Alerts</h2>
        <p className="text-[#6b7f8e] mt-1">Create and manage alert rules for your portfolio</p>
      </div>

      <Tabs
        tabs={[
          { id: "rules", label: "My Rules" },
          { id: "create", label: "Create Rule" },
        ]}
        activeTab={activeTab}
        onTabChange={setActiveTab}
      />

      {activeTab === "rules" ? <MyRulesTab /> : <CreateRuleTab />}
    </div>
  );
}