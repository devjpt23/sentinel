"use client";

import { useCallback } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Plus, Trash2, Loader2, ChevronUp, ChevronDown } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Separator } from "@/components/ui/separator";
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription,
} from "@/components/ui/dialog";
import { toast } from "sonner";
import { api } from "@/lib/api-client";
import type { AlertRule, AlertCondition } from "@/types/api";
import { useAlertBuilder } from "@/stores/alert-builder-store";
import { SIGNAL_CATALOG, SIGNAL_CATEGORIES, SIGNAL_CATALOG_BY_CATEGORY, getSignalById } from "@/lib/signal-catalog";

const OPERATORS = [">", "<", ">=", "<=", "==", "crosses_above", "crosses_below", "touches_upper", "touches_lower"];

interface AlertRuleDialogProps {
  userId: number;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  editingRule?: AlertRule | null;
  onCreated?: () => void;
  existingRuleNames?: string[];
}

export default function AlertRuleDialog({
  userId,
  open,
  onOpenChange,
  editingRule,
  onCreated,
  existingRuleNames = [],
}: AlertRuleDialogProps) {
  const queryClient = useQueryClient();
  const {
    name, severity, scope, ticker, conditions, logic,
    setName, setSeverity, setScope, setTicker,
    addCondition, updateCondition, removeCondition, moveCondition, setLogic, reset,
  } = useAlertBuilder();

  const createMutation = useMutation({
    mutationFn: () => {
      const finalName = name.trim() || autoGenerateName();
      // Check for duplicate on create (not on edit)
      if (!editingRule && existingRuleNames.includes(finalName)) {
        throw new Error("DUPLICATE");
      }
      const body = {
        name: finalName,
        severity,
        scope,
        ...(scope === "single" ? { ticker } : {}),
        conditions: conditions.filter((c) => c.signal_id),
        logic,
      };
      if (editingRule) {
        return api.put<{ ok: boolean }>(`/api/alerts/${userId}/${editingRule.id}`, body);
      }
      return api.post<{ ok: boolean; rule_id?: string }>(`/api/alerts/${userId}`, body);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["alerts"] });
      reset();
      onCreated?.();
      toast.success(editingRule ? "Alert rule updated" : "Alert rule created");
      onOpenChange(false);
    },
    onError: (err) => {
      if (err instanceof Error && err.message === "DUPLICATE") {
        const finalName = name.trim() || autoGenerateName();
        toast.warning(`An alert rule named "${finalName}" already exists`, {
          duration: 5000,
        });
      } else {
        toast.error(`Failed to ${editingRule ? "update" : "create"} alert rule`);
      }
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

  const handleClose = useCallback(() => {
    reset();
    onOpenChange(false);
  }, [reset, onOpenChange]);

  return (
    <Dialog open={open} onOpenChange={(o) => { if (!o) handleClose(); }}>
      <DialogContent className="max-w-2xl max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>{editingRule ? "Edit Alert Rule" : "Create Custom Rule"}</DialogTitle>
          <DialogDescription>
            {editingRule ? "Modify the conditions for this alert rule" : "Create a custom alert rule with your own conditions"}
          </DialogDescription>
        </DialogHeader>

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
                    <div className="flex items-center gap-2">
                      <span className="text-sm text-[#6b7f8e]">Condition {idx + 1}</span>
                      {conditions.length > 1 && (
                        <div className="flex gap-0.5">
                          <Button variant="ghost" size="sm" className="h-5 w-5 p-0 text-[#3a5570] hover:text-[#6b7f8e]" disabled={idx === 0} onClick={() => moveCondition(idx, "up")}>
                            <ChevronUp className="h-3.5 w-3.5" />
                          </Button>
                          <Button variant="ghost" size="sm" className="h-5 w-5 p-0 text-[#3a5570] hover:text-[#6b7f8e]" disabled={idx === conditions.length - 1} onClick={() => moveCondition(idx, "down")}>
                            <ChevronDown className="h-3.5 w-3.5" />
                          </Button>
                        </div>
                      )}
                    </div>
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

          {/* Auto-name preview */}
          {!name.trim() && conditions.some((c) => c.signal_id) && (
            <div className="rounded-md border border-[#1e2d3a] bg-[#0d1319]/50 px-4 py-2.5">
              <div className="flex items-center gap-2">
                <span className="text-xs text-[#3a5570] font-medium">Auto-generated rule name:</span>
                <span className="text-sm text-[#84cc16]">{autoGenerateName()}</span>
              </div>
            </div>
          )}

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
            {editingRule ? "Update Rule" : "Save Rule"}
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}
