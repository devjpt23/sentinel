"use client";

import { useState, useMemo } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { flexRender, getCoreRowModel, getSortedRowModel, getPaginationRowModel, useReactTable, type ColumnDef } from "@tanstack/react-table";
import { Bell, CheckCircle, AlertCircle, Info, TriangleAlert, MailCheck, Trash2, Lock } from "lucide-react";
import { api } from "@/lib/api-client";
import { formatRelativeTime } from "@/lib/utils";
import { useUser } from "@/hooks/use-watchlist";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import Link from "next/link";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Skeleton } from "@/components/ui/skeleton";
import { toast } from "sonner";

interface NotificationItem { id: string; ticker: string; body: string; severity: "info" | "warning" | "critical"; created_at: string; read: boolean; dismissed: boolean; }


function severityIcon(severity: string) {
  switch (severity) {
    case "info": return <Info className="h-4 w-4 text-[#84cc16]" />;
    case "warning": return <TriangleAlert className="h-4 w-4 text-yellow-400" />;
    case "critical": return <AlertCircle className="h-4 w-4 text-red-400" />;
    default: return <Bell className="h-4 w-4 text-[#6b7f8e]" />;
  }
}

function severityBadgeClass(severity: string) {
  switch (severity) {
    case "info": return "border-[#84cc16]/30 bg-[#84cc16]/20 text-[#84cc16]";
    case "warning": return "border-yellow-500/30 bg-yellow-500/20 text-yellow-400";
    case "critical": return "border-red-500/30 bg-red-500/20 text-red-400";
    default: return "border-[#1e2d3a] bg-[#1a2a38] text-[#6b7f8e]";
  }
}

function AuthRequired() {
  return (
    <div className="flex items-center justify-center min-h-[60vh]">
      <Card className="max-w-md">
        <CardHeader className="text-center">
          <Lock className="h-12 w-12 mx-auto mb-2 text-[#6b7f8e]" />
          <CardTitle className="text-[#f0f4f0]">Access Denied</CardTitle>
          <CardDescription>You must be signed in to view notifications.</CardDescription>
        </CardHeader>
        <CardContent className="text-center">
          <p className="text-sm text-[#6b7f8e] mb-4">Sign in or create an account to see your notifications.</p>
          <Link href="/login" className="inline-flex items-center justify-center rounded-md text-sm font-medium h-10 px-4 py-2 bg-[#84cc16] text-[#0a0e13] hover:bg-[#74b810]">
            Sign In
          </Link>
        </CardContent>
      </Card>
    </div>
  );
}

export default function NotificationsPage() {
  const [unreadOnly, setUnreadOnly] = useState(false);
  const [severityFilter, setSeverityFilter] = useState("all");
  const [tickerFilter, setTickerFilter] = useState("");
  const [page, setPage] = useState(0);
  const pageSize = 20;
  const queryClient = useQueryClient();
  const { data: userData, isLoading: userLoading } = useUser();

  const { data, isLoading } = useQuery({
    queryKey: ["notifications", userData?.id ?? 0, unreadOnly, severityFilter, tickerFilter],
    queryFn: () => {
      const params: Record<string, string | number | boolean> = { limit: 200 };
      if (unreadOnly) params.unread_only = true;
      return api.get<{ notifications: NotificationItem[] }>("/api/notifications/" + (userData?.id ?? 0), { params });
    },
    refetchInterval: unreadOnly ? 60000 : undefined,
    enabled: !!userData,
  });

  const { data: unreadData } = useQuery({
    queryKey: ["unread-count", userData?.id ?? 0],
    queryFn: () => api.get<{ count: number }>("/api/notifications/" + (userData?.id ?? 0) + "/unread-count"),
    refetchInterval: 60000,
    enabled: !!userData,
  });

  const markReadMutation = useMutation({
    mutationFn: (id: string) => api.post<{ ok: boolean }>("/api/notifications/" + (userData?.id ?? 0) + "/mark-read", { notification_id: id }),
    onSuccess: () => { queryClient.invalidateQueries({ queryKey: ["notifications"] }); queryClient.invalidateQueries({ queryKey: ["unread-count"] }); toast.success("Marked as read"); },
  });

  const markAllReadMutation = useMutation({
    mutationFn: () => api.post<{ ok: boolean }>("/api/notifications/" + (userData?.id ?? 0) + "/mark-all-read"),
    onSuccess: () => { queryClient.invalidateQueries({ queryKey: ["notifications"] }); queryClient.invalidateQueries({ queryKey: ["unread-count"] }); toast.success("All marked as read"); },
  });

  const dismissMutation = useMutation({
    mutationFn: (id: string) => api.post<{ ok: boolean }>("/api/notifications/" + (userData?.id ?? 0) + "/dismiss", { notification_id: id }),
    onSuccess: () => { queryClient.invalidateQueries({ queryKey: ["notifications"] }); queryClient.invalidateQueries({ queryKey: ["unread-count"] }); toast.success("Notification dismissed"); },
  });

  const allNotifications = useMemo(() => {
    let items = data?.notifications ?? [];
    if (severityFilter !== "all") items = items.filter((n) => n.severity === severityFilter);
    if (tickerFilter) items = items.filter((n) => n.ticker.toLowerCase().includes(tickerFilter.toLowerCase()));
    return items;
  }, [data, severityFilter, tickerFilter]);

  const paginated = allNotifications.slice(page * pageSize, (page + 1) * pageSize);
  const totalPages = Math.ceil(allNotifications.length / pageSize);

  const columns = useMemo<ColumnDef<NotificationItem>[]>(() => [
    { id: "severity", header: "", cell: (info) => severityIcon(info.row.original.severity) },
    { accessorKey: "ticker", header: "Ticker", cell: (info) => <span className="font-mono font-medium text-[#f0f4f0]">{info.getValue<string>()}</span> },
    { accessorKey: "body", header: "Message", cell: (info) => <span className={info.row.original.read ? "text-[#6b7f8e]" : "text-[#c8d8e4] font-medium"}>{info.getValue<string>()}</span> },
    { id: "severity-badge", accessorKey: "severity", header: "Severity", cell: (info) => <Badge variant="outline" className={severityBadgeClass(info.getValue<string>())}>{info.getValue<string>()}</Badge> },
    { accessorKey: "created_at", header: "Time", cell: (info) => <span className="text-[#6b7f8e] text-sm">{formatRelativeTime(info.getValue<string>())}</span> },
    { id: "actions", header: "", cell: (info) => (
      <div className="flex gap-1">
        {!info.row.original.read && (<Button size="sm" variant="ghost" className="h-7 w-7 p-0" onClick={() => markReadMutation.mutate(info.row.original.id)}><CheckCircle className="h-3.5 w-3.5 text-[#84cc16]" /></Button>)}
        <Button size="sm" variant="ghost" className="h-7 w-7 p-0" onClick={() => dismissMutation.mutate(info.row.original.id)}><Trash2 className="h-3.5 w-3.5 text-[#6b7f8e]" /></Button>
      </div>
    ) },
  ], [markReadMutation, dismissMutation]);

  const table = useReactTable({ data: paginated, columns, getCoreRowModel: getCoreRowModel(), getSortedRowModel: getSortedRowModel(), getPaginationRowModel: getPaginationRowModel() });

  if (userLoading) {
    return <div className="flex items-center justify-center min-h-[60vh]"><Skeleton className="h-8 w-48" /></div>;
  }

  if (!userData) {
    return <AuthRequired />;
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold text-[#f0f4f0]">Notifications</h2>
          <p className="text-[#6b7f8e] mt-1">{unreadData?.count != null && unreadData.count > 0 ? unreadData.count + " unread notification" + (unreadData.count > 1 ? "s" : "") : "All caught up"}</p>
        </div>
        <Button variant="outline" size="sm" onClick={() => markAllReadMutation.mutate()} disabled={markAllReadMutation.isPending}>
          <MailCheck className="h-4 w-4 mr-1" /> Mark All Read
        </Button>
      </div>
      <div className="flex gap-4 items-end flex-wrap">
        <div className="flex items-center gap-2">
          <Checkbox checked={unreadOnly} onCheckedChange={(c) => setUnreadOnly(!!c)} />
          <span className="text-sm text-[#6b7f8e]">Unread only</span>
        </div>
        <div className="w-40">
          <label className="text-xs text-[#6b7f8e] mb-1 block">Severity</label>
          <Select value={severityFilter} onValueChange={setSeverityFilter}>
            <SelectTrigger><SelectValue /></SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All</SelectItem>
              <SelectItem value="info">Info</SelectItem>
              <SelectItem value="warning">Warning</SelectItem>
              <SelectItem value="critical">Critical</SelectItem>
            </SelectContent>
          </Select>
        </div>
        <div className="w-40">
          <label className="text-xs text-[#6b7f8e] mb-1 block">Ticker</label>
          <Input placeholder="Filter ticker" value={tickerFilter} onChange={(e) => setTickerFilter(e.target.value)} />
        </div>
      </div>
      <div className="rounded-lg border border-[#1e2d3a]">
        {isLoading ? (<div className="p-8 space-y-3">{Array.from({ length: 5 }).map((_, i) => (<Skeleton key={i} className="h-12 w-full" />))}</div>) : (<>
          <Table>
            <TableHeader>{table.getHeaderGroups().map((hg) => (<TableRow key={hg.id}>{hg.headers.map((h) => (<TableHead key={h.id}>{h.isPlaceholder ? null : flexRender(h.column.columnDef.header, h.getContext())}</TableHead>))}</TableRow>))}</TableHeader>
            <TableBody>{table.getRowModel().rows.length === 0 ? (<TableRow><TableCell colSpan={columns.length} className="text-center text-[#6b7f8e] py-8">No notifications</TableCell></TableRow>) : table.getRowModel().rows.map((row) => (<TableRow key={row.original.id} className={row.original.read ? "" : "bg-[#1a2a38]/30"}>{row.getVisibleCells().map((cell) => (<TableCell key={cell.id}>{flexRender(cell.column.columnDef.cell, cell.getContext())}</TableCell>))}</TableRow>))}</TableBody>
          </Table>
          {totalPages > 1 && (
            <div className="flex items-center justify-between px-4 py-3 border-t border-[#1e2d3a]">
              <span className="text-sm text-[#6b7f8e]">Page {page + 1} of {totalPages} ({allNotifications.length} total)</span>
              <div className="flex gap-2">
                <Button variant="outline" size="sm" onClick={() => setPage((p) => Math.max(0, p - 1))} disabled={page === 0}>Previous</Button>
                <Button variant="outline" size="sm" onClick={() => setPage((p) => Math.min(totalPages - 1, p + 1))} disabled={page >= totalPages - 1}>Next</Button>
              </div>
            </div>
          )}
        </>)}
      </div>
    </div>
  );
}