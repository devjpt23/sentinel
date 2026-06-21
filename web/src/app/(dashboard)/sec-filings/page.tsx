"use client";

import { useState, useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import { flexRender, getCoreRowModel, getSortedRowModel, getPaginationRowModel, useReactTable, type SortingState, type ColumnDef } from "@tanstack/react-table";
import { ArrowUpDown, ExternalLink } from "lucide-react";
import { api } from "@/lib/api-client";
import { useDebounce } from "@/hooks/use-debounce";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Tabs } from "@/components/ui/tabs";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Skeleton } from "@/components/ui/skeleton";

interface Filing { ticker: string; type: string; date: string; link: string; }
interface InsiderTrade { ticker: string; name: string; title: string; transaction: "Buy" | "Sell"; shares: number; value: number; date: string; }

function typeBadgeColor(type: string): string {
  if (type === "10-K") return "border-[#84cc16]/30 bg-[#84cc16]/20 text-[#84cc16]";
  if (type === "10-Q") return "border-purple-500/30 bg-purple-500/20 text-purple-400";
  if (type === "8-K") return "border-yellow-500/30 bg-yellow-500/20 text-yellow-400";
  return "border-[#1e2d3a] bg-[#1a2a38] text-[#6b7f8e]";
}

export default function SECFilingsPage() {
  const [activeTab, setActiveTab] = useState("filings");
  const [tickerSearch, setTickerSearch] = useState("");
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");
  const [sorting, setSorting] = useState<SortingState>([]);
  const debouncedTicker = useDebounce(tickerSearch, 400);

  const filingsQuery = useQuery({
    queryKey: ["filings", debouncedTicker],
    queryFn: () => api.get<{ filings: Filing[] }>(debouncedTicker ? "/api/data/" + debouncedTicker + "/filings" : "/api/data/AAPL/filings"),
    enabled: activeTab === "filings",
  });

  const insiderQuery = useQuery({
    queryKey: ["insider", debouncedTicker],
    queryFn: () => api.get<{ insider: InsiderTrade[] }>(debouncedTicker ? "/api/data/" + debouncedTicker + "/insider" : "/api/data/AAPL/insider"),
    enabled: activeTab === "insider",
  });

  const filings = useMemo(() => {
    let data = filingsQuery.data?.filings ?? [];
    if (dateFrom) data = data.filter((f) => f.date >= dateFrom);
    if (dateTo) data = data.filter((f) => f.date <= dateTo);
    return data;
  }, [filingsQuery.data, dateFrom, dateTo]);

  const filingsColumns = useMemo<ColumnDef<Filing>[]>(() => [
    { accessorKey: "ticker", header: "Ticker", cell: (info) => <span className="font-mono font-medium text-[#f0f4f0]">{info.getValue<string>()}</span> },
    { accessorKey: "type", header: "Type", cell: (info) => <Badge variant="outline" className={typeBadgeColor(info.getValue<string>())}>{info.getValue<string>()}</Badge> },
    { accessorKey: "date", header: ({ column }) => (<span className="flex items-center gap-1 cursor-pointer" onClick={() => column.toggleSorting()}>Date <ArrowUpDown className="h-3 w-3" /></span>), cell: (info) => new Date(info.getValue<string>()).toLocaleDateString() },
    { accessorKey: "link", header: "Link", cell: (info) => (<a href={info.getValue<string>()} target="_blank" rel="noopener noreferrer" className="text-[#84cc16] hover:text-[#65a30d] flex items-center gap-1 transition-colors">View <ExternalLink className="h-3 w-3" /></a>) },
  ], []);

  const insiderColumns = useMemo<ColumnDef<InsiderTrade>[]>(() => [
    { accessorKey: "ticker", header: "Ticker", cell: (info) => <span className="font-mono font-medium text-[#f0f4f0]">{info.getValue<string>()}</span> },
    { accessorKey: "name", header: "Name", cell: (info) => <span className="text-[#c8d8e4]">{info.getValue<string>()}</span> },
    { accessorKey: "title", header: "Title", cell: (info) => <span className="text-[#6b7f8e] text-sm">{info.getValue<string>()}</span> },
    { accessorKey: "transaction", header: "Transaction", cell: (info) => { const v = info.getValue<string>(); return (<Badge variant="outline" className={v === "Buy" ? "border-[#84cc16]/30 bg-[#84cc16]/20 text-[#84cc16]" : "border-red-500/30 bg-red-500/20 text-red-400"}>{v}</Badge>); } },
    { accessorKey: "shares", header: "Shares", cell: (info) => info.getValue<number>().toLocaleString() },
    { accessorKey: "value", header: "Value", cell: (info) => "$" + info.getValue<number>().toLocaleString() },
    { accessorKey: "date", header: ({ column }) => (<span className="flex items-center gap-1 cursor-pointer" onClick={() => column.toggleSorting()}>Date <ArrowUpDown className="h-3 w-3" /></span>), cell: (info) => new Date(info.getValue<string>()).toLocaleDateString() },
  ], []);

  const filingsTable = useReactTable({ data: filings, columns: filingsColumns, state: { sorting }, onSortingChange: setSorting, getCoreRowModel: getCoreRowModel(), getSortedRowModel: getSortedRowModel(), getPaginationRowModel: getPaginationRowModel(), initialState: { pagination: { pageSize: 20 } } });
  const insiderTable = useReactTable({ data: insiderQuery.data?.insider ?? [], columns: insiderColumns, state: { sorting }, onSortingChange: setSorting, getCoreRowModel: getCoreRowModel(), getSortedRowModel: getSortedRowModel(), getPaginationRowModel: getPaginationRowModel(), initialState: { pagination: { pageSize: 20 } } });

  const isLoading = activeTab === "filings" ? filingsQuery.isLoading : insiderQuery.isLoading;

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-bold text-[#f0f4f0]">SEC Filings & Insider Trading</h2>
        <p className="text-[#6b7f8e] mt-1">Track company filings and insider transactions</p>
      </div>
      <div className="flex gap-4 items-end">
        <div className="flex-1 max-w-xs">
          <label className="text-xs text-[#6b7f8e] mb-1 block">Search by Ticker</label>
          <Input placeholder="e.g. AAPL" value={tickerSearch} onChange={(e) => setTickerSearch(e.target.value.toUpperCase())} />
        </div>
        {activeTab === "filings" && (<>
          <div><label className="text-xs text-[#6b7f8e] mb-1 block">From Date</label><Input type="date" value={dateFrom} onChange={(e) => setDateFrom(e.target.value)} /></div>
          <div><label className="text-xs text-[#6b7f8e] mb-1 block">To Date</label><Input type="date" value={dateTo} onChange={(e) => setDateTo(e.target.value)} /></div>
        </>)}
      </div>
      <Tabs tabs={[{ id: "filings", label: "Filings" }, { id: "insider", label: "Insider Trading" }]} activeTab={activeTab} onTabChange={setActiveTab} />
      <div className="rounded-lg border border-[#1e2d3a]">
        {isLoading ? (<div className="p-8 space-y-3">{Array.from({ length: 5 }).map((_, i) => (<Skeleton key={i} className="h-10 w-full" />))}</div>) : activeTab === "filings" ? (<>
          <Table>
            <TableHeader>{filingsTable.getHeaderGroups().map((hg) => (<TableRow key={hg.id}>{hg.headers.map((h) => (<TableHead key={h.id}>{h.isPlaceholder ? null : flexRender(h.column.columnDef.header, h.getContext())}</TableHead>))}</TableRow>))}</TableHeader>
            <TableBody>{filingsTable.getRowModel().rows.length === 0 ? (<TableRow><TableCell colSpan={filingsColumns.length} className="text-center text-[#6b7f8e] py-8">No filings found</TableCell></TableRow>) : filingsTable.getRowModel().rows.map((row) => (<TableRow key={row.id}>{row.getVisibleCells().map((cell) => (<TableCell key={cell.id}>{flexRender(cell.column.columnDef.cell, cell.getContext())}</TableCell>))}</TableRow>))}</TableBody>
          </Table>
          <div className="flex items-center justify-between px-4 py-3 border-t border-[#1e2d3a]">
            <span className="text-sm text-[#6b7f8e]">{filingsTable.getRowModel().rows.length} results</span>
            <div className="flex gap-2">
              <Button variant="outline" size="sm" onClick={() => filingsTable.previousPage()} disabled={!filingsTable.getCanPreviousPage()}>Previous</Button>
              <Button variant="outline" size="sm" onClick={() => filingsTable.nextPage()} disabled={!filingsTable.getCanNextPage()}>Next</Button>
            </div>
          </div>
        </>) : (<>
          <Table>
            <TableHeader>{insiderTable.getHeaderGroups().map((hg) => (<TableRow key={hg.id}>{hg.headers.map((h) => (<TableHead key={h.id}>{h.isPlaceholder ? null : flexRender(h.column.columnDef.header, h.getContext())}</TableHead>))}</TableRow>))}</TableHeader>
            <TableBody>{insiderTable.getRowModel().rows.length === 0 ? (<TableRow><TableCell colSpan={insiderColumns.length} className="text-center text-[#6b7f8e] py-8">No insider trades found</TableCell></TableRow>) : insiderTable.getRowModel().rows.map((row) => (<TableRow key={row.id}>{row.getVisibleCells().map((cell) => (<TableCell key={cell.id}>{flexRender(cell.column.columnDef.cell, cell.getContext())}</TableCell>))}</TableRow>))}</TableBody>
          </Table>
          <div className="flex items-center justify-between px-4 py-3 border-t border-[#1e2d3a]">
            <span className="text-sm text-[#6b7f8e]">{insiderTable.getRowModel().rows.length} results</span>
            <div className="flex gap-2">
              <Button variant="outline" size="sm" onClick={() => insiderTable.previousPage()} disabled={!insiderTable.getCanPreviousPage()}>Previous</Button>
              <Button variant="outline" size="sm" onClick={() => insiderTable.nextPage()} disabled={!insiderTable.getCanNextPage()}>Next</Button>
            </div>
          </div>
        </>)}
      </div>
    </div>
  );
}