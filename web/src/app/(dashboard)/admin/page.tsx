"use client";

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Check, X, Trash2, RefreshCw, Database, Lock } from "lucide-react";
import Link from "next/link";
import { api } from "@/lib/api-client";
import { formatRelativeTime } from "@/lib/utils";
import { useUser } from "@/hooks/use-watchlist";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { toast } from "sonner";

interface AdminUser {
  id: number;
  username: string;
  email: string | null;
  telegram_chat_id: string | null;
  last_login: string | null;
  created_at: string;
}

function StatCard({ label, value, description }: { label: string; value: string | number; description: string }) {
  return (
    <Card>
      <CardHeader className="pb-2">
        <CardDescription>{label}</CardDescription>
        <CardTitle className="text-3xl text-[#f0f4f0]">{value}</CardTitle>
      </CardHeader>
      <CardContent>
        <p className="text-xs text-[#6b7f8e]">{description}</p>
      </CardContent>
    </Card>
  );
}

export default function AdminPage() {
  const queryClient = useQueryClient();

  const { data: meData, isLoading: meLoading, error: meError } = useUser();
  const isAuthenticated = !meError && meData;

  const { data: usersData, isLoading: usersLoading } = useQuery({
    queryKey: ["admin-users"],
    queryFn: () => api.get<{ users: AdminUser[] }>("/api/user"),
    enabled: !!isAuthenticated,
  });

  const users = (usersData?.users ?? []) as AdminUser[];

  // Compute stats from notifications
  const { data: notifData } = useQuery({
    queryKey: ["admin-stats"],
    queryFn: () => api.get<{ total: number; unread: number }>("/api/notifications/stats"),
    retry: false,
    enabled: !!isAuthenticated,
  });

  // Maintenance mutations
  const pruneNotifications = useMutation({
    mutationFn: () => api.post<{ ok: boolean }>("/api/admin/prune/notifications"),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["admin-stats"] });
      toast.success("Old notifications pruned");
    },
  });

  const pruneCheckRuns = useMutation({
    mutationFn: () => api.post<{ ok: boolean }>("/api/admin/prune/check-runs"),
    onSuccess: () => {
      toast.success("Old check runs pruned");
    },
  });

  const rescanUsers = useMutation({
    mutationFn: () => api.post<{ ok: boolean }>("/api/admin/rescan"),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["admin-users"] });
      toast.success("User rescan triggered");
    },
  });

  if (meLoading) {
    return <div className="flex items-center justify-center min-h-[60vh]"><Skeleton className="h-8 w-48" /></div>;
  }

  if (!isAuthenticated) {
    return (
      <div className="flex items-center justify-center min-h-[60vh]">
        <Card className="max-w-md">
          <CardHeader className="text-center">
            <Lock className="h-12 w-12 mx-auto mb-2 text-[#6b7f8e]" />
            <CardTitle className="text-[#f0f4f0]">Access Denied</CardTitle>
            <CardDescription>You must be signed in to access the admin panel.</CardDescription>
          </CardHeader>
          <CardContent className="text-center">
            <p className="text-sm text-[#6b7f8e] mb-4">Sign in or create an account to view system administration tools.</p>
            <Link href="/login" className="inline-flex items-center justify-center rounded-md text-sm font-medium h-10 px-4 py-2 bg-[#84cc16] text-[#0a0e13] hover:bg-[#74b810]">
              Sign In
            </Link>
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-bold text-[#f0f4f0]">Admin</h2>
        <p className="text-[#6b7f8e] mt-1">System administration and maintenance</p>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <StatCard
          label="Total Notifications"
          value={notifData?.total ?? "--"}
          description="All time notifications sent"
        />
        <StatCard
          label="Unread Notifications"
          value={notifData?.unread ?? "--"}
          description="Currently unread across all users"
        />
        <StatCard
          label="Total Users"
          value={users.length || "--"}
          description="Registered users"
        />
      </div>

      {/* Maintenance */}
      <Card>
        <CardHeader>
          <CardTitle className="text-[#f0f4f0] flex items-center gap-2">
            <Database className="h-5 w-5" />
            Database Maintenance
          </CardTitle>
          <CardDescription>Run cleanup operations on the database</CardDescription>
        </CardHeader>
        <CardContent className="flex gap-3 flex-wrap">
          <Button variant="outline" size="sm" onClick={() => pruneNotifications.mutate()} disabled={pruneNotifications.isPending}>
            <Trash2 className="h-4 w-4 mr-1" />
            Prune Old Notifications
          </Button>
          <Button variant="outline" size="sm" onClick={() => pruneCheckRuns.mutate()} disabled={pruneCheckRuns.isPending}>
            <Trash2 className="h-4 w-4 mr-1" />
            Prune Check Runs
          </Button>
          <Button variant="outline" size="sm" onClick={() => rescanUsers.mutate()} disabled={rescanUsers.isPending}>
            <RefreshCw className="h-4 w-4 mr-1" />
            Rescan Users
          </Button>
        </CardContent>
      </Card>

      {/* Users Table */}
      <Card>
        <CardHeader>
          <CardTitle className="text-[#f0f4f0]">Users</CardTitle>
          <CardDescription>All registered users</CardDescription>
        </CardHeader>
        <CardContent>
          {usersLoading ? (
            <div className="space-y-3">
              {Array.from({ length: 5 }).map((_, i) => (
                <Skeleton key={i} className="h-10 w-full" />
              ))}
            </div>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>ID</TableHead>
                  <TableHead>Username</TableHead>
                  <TableHead>Email</TableHead>
                  <TableHead>Telegram</TableHead>
                  <TableHead>Last Login</TableHead>
                  <TableHead>Created</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {users.length === 0 ? (
                  <TableRow>
                    <TableCell colSpan={6} className="text-center text-[#6b7f8e] py-8">
                      No users found
                    </TableCell>
                  </TableRow>
                ) : (
                  users.map((user) => (
                    <TableRow key={user.id}>
                      <TableCell className="text-[#6b7f8e]">{user.id}</TableCell>
                      <TableCell className="font-medium text-[#f0f4f0]">{user.username}</TableCell>
                      <TableCell className="text-[#6b7f8e]">{user.email ?? "N/A"}</TableCell>
                      <TableCell>
                        {user.telegram_chat_id ? (
                          <Badge variant="outline" className="border-[#84cc16]/30 bg-[#84cc16]/20 text-[#84cc16]">
                            <Check className="h-3 w-3 mr-1" /> Connected
                          </Badge>
                        ) : (
                          <Badge variant="outline" className="border-[#1e2d3a] text-[#6b7f8e]">
                            <X className="h-3 w-3 mr-1" /> Not Connected
                          </Badge>
                        )}
                      </TableCell>
                      <TableCell className="text-[#6b7f8e] text-sm">
                        {user.last_login ? formatRelativeTime(user.last_login) : "Never"}
                      </TableCell>
                      <TableCell className="text-[#6b7f8e] text-sm">
                        {formatRelativeTime(user.created_at)}
                      </TableCell>
                    </TableRow>
                  ))
                )}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>
    </div>
  );
}