"use client";

import { useState, useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import { flexRender, getCoreRowModel, getSortedRowModel, getPaginationRowModel, useReactTable, type SortingState, type ColumnDef, createColumnHelper } from "@tanstack/react-table";
import { ArrowUpDown, ArrowUp, ArrowDown } from "lucide-react";
import Link from "next/link";
import { api } from "@/lib/api-client";
import { useDebounce } from "@/hooks/use-debounce";
import { formatCurrency, formatNumber, formatPct, getHealthBg, getVerdictInfo } from "@/lib/utils";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Skeleton } from "@/components/ui/skeleton";

const COUNTRIES = [
  { value: "", label: "All Countries" },
  { value: "US", label: "United States" },
  { value: "CA", label: "Canada" },
  { value: "UK", label: "United Kingdom" },
  { value: "DE", label: "Germany" },
  { value: "FR", label: "France" },
  { value: "JP", label: "Japan" },
  { value: "CN", label: "China" },
  { value: "IN", label: "India" },
  { value: "AU", label: "Australia" },
  { value: "BR", label: "Brazil" },
  { value: "KR", label: "South Korea" },
  { value: "MX", label: "Mexico" },
  { value: "ES", label: "Spain" },
  { value: "IT", label: "Italy" },
  { value: "NL", label: "Netherlands" },
  { value: "SE", label: "Sweden" },
  { value: "CH", label: "Switzerland" },
];

const SORT_OPTIONS = [
  { value: "market_cap", label: "Market Cap" },
  { value: "pe", label: "P/E Ratio" },
  { value: "volume", label: "Volume" },
  { value: "price", label: "Price" },
  { value: "change", label: "Change" },
  { value: "health", label: "Health Score" },
];

interface ScreenerRow {
  ticker: string;
  name: string;
  price: number;
  marketCap: number;
  pe: number | null;
  volume: number;
  change: number;
  healthScore: number;
  verdict: string;
}

const columnHelper = createColumnHelper<ScreenerRow>();

export default function ScreenerPage() {
  const [country, setCountry] = useState("");
  const [sortBy, setSortBy] = useState("market_cap");
  const [limit, setLimit] = useState(25);
  const [peMin, setPeMin] = useState("");
  const [peMax, setPeMax] = useState("");
  const [mcMin, setMcMin] = useState("");
  const [mcMax, setMcMax] = useState("");
  const [sorting, setSorting] = useState<SortingState>([]);
  const [globalFilter, setGlobalFilter] = useState("");

  const debouncedPeMin = useDebounce(peMin, 400);
  const debouncedPeMax = useDebounce(peMax, 400);
  const debouncedMcMin = useDebounce(mcMin, 400);
  const debouncedMcMax = useDebounce(mcMax, 400);
  const debouncedFilter = useDebounce(globalFilter, 300);

  const { data, isLoading, error } = useQuery({
    queryKey: ["screener", country, sortBy, limit, debouncedPeMin, debouncedPeMax, debouncedMcMin, debouncedMcMax],
    queryFn: () => {
      const params: Record<string, string | number | boolean> = { sort: sortBy, limit };
      if (country) params.country = country;
      if (debouncedPeMin) params.pe_min = Number(debouncedPeMin);
      if (debouncedPeMax) params.pe_max = Number(debouncedPeMax);
      if (debouncedMcMin) params.market_cap_min = Number(debouncedMcMin);
      if (debouncedMcMax) params.market_cap_max = Number(debouncedMcMax);
      return api.get<{ stocks: Record<string, unknown>[] }>("/api/screener", { params });
    },
  });

  const results = useMemo(() => {
    const raw: ScreenerRow[] = (data?.stocks ?? []).map((s) => ({
      ticker: (s.symbol as string) || "",
      name: (s.name as string) || "",
      price: Number(s.price) || 0,
      marketCap: Number(s.market_cap) || 0,
      pe: s.pe != null ? Number(s.pe) : null,
      volume: Number(s.volume) || 0,
      change: Number(s.percent_change) || 0,
      healthScore: s.health_score != null ? Number(s.health_score) : 50,
      verdict: (s.verdict as string) || "Hold",
    }));
    if (!debouncedFilter) return raw;
    const q = debouncedFilter.toLowerCase();
    return raw.filter((r) => r.ticker.toLowerCase().includes(q) || r.name.toLowerCase().includes(q));
  }, [data, debouncedFilter]);

  const columns = useMemo(() => [
    columnHelper.accessor("ticker", {
      header: ({ column }) => (<span className="flex items-center gap-1 cursor-pointer" onClick={() => column.toggleSorting()}>Ticker <ArrowUpDown className="h-3 w-3" /></span>),
      cell: (info) => (<Link href={"/company/" + info.getValue()} className="text-[#84cc16] hover:text-[#65a30d] font-medium transition-colors">{info.getValue()}</Link>),
    }),
    columnHelper.accessor("name", {
      header: "Name",
      cell: (info) => <span className="text-[#6b7f8e]">{info.getValue()}</span>,
    }),
    columnHelper.accessor("price", {
      header: ({ column }) => (<span className="flex items-center gap-1 cursor-pointer" onClick={() => column.toggleSorting()}>Price <ArrowUpDown className="h-3 w-3" /></span>),
      cell: (info) => formatCurrency(info.getValue()),
    }),
    columnHelper.accessor("marketCap", {
      header: ({ column }) => (<span className="flex items-center gap-1 cursor-pointer" onClick={() => column.toggleSorting()}>Mkt Cap <ArrowUpDown className="h-3 w-3" /></span>),
      cell: (info) => formatCurrency(info.getValue()),
    }),
    columnHelper.accessor("pe", {
      header: ({ column }) => (<span className="flex items-center gap-1 cursor-pointer" onClick={() => column.toggleSorting()}>P/E <ArrowUpDown className="h-3 w-3" /></span>),
      cell: (info) => { const v = info.getValue(); return v != null ? v.toFixed(2) : "N/A"; },
    }),
    columnHelper.accessor("volume", {
      header: ({ column }) => (<span className="flex items-center gap-1 cursor-pointer" onClick={() => column.toggleSorting()}>Volume <ArrowUpDown className="h-3 w-3" /></span>),
      cell: (info) => formatNumber(info.getValue()),
    }),
    columnHelper.accessor("change", {
      header: ({ column }) => (<span className="flex items-center gap-1 cursor-pointer" onClick={() => column.toggleSorting()}>Change <ArrowUpDown className="h-3 w-3" /></span>),
      cell: (info) => {
        const v = info.getValue();
        const c = v >= 0 ? "text-[#84cc16]" : "text-red-400";
        const Ic = v >= 0 ? ArrowUp : ArrowDown;
        return (<span className={"flex items-center gap-1 " + c}><Ic className="h-3 w-3" />{formatPct(v)}</span>);
      },
    }),
    columnHelper.accessor("healthScore", {
      header: ({ column }) => (<span className="flex items-center gap-1 cursor-pointer" onClick={() => column.toggleSorting()}>Health <ArrowUpDown className="h-3 w-3" /></span>),
      cell: (info) => <Badge className={getHealthBg(info.getValue())}>{info.getValue()}</Badge>,
    }),
    columnHelper.accessor("verdict", {
      header: "Verdict",
      cell: (info) => {
        const vi = getVerdictInfo(info.getValue());
        return <Badge variant="outline" className={vi.color + " " + vi.bg}>{info.getValue()}</Badge>;
      },
    }),
  ], []);

  const table = useReactTable({
    data: results,
    columns,
    state: { sorting },
    onSortingChange: setSorting,
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: getSortedRowModel(),
    getPaginationRowModel: getPaginationRowModel(),
    initialState: { pagination: { pageSize: 25 } },
  });

  if (error) {
    return (<div className="rounded-lg border border-red-500/30 bg-red-500/10 p-6 text-center"><p className="text-red-400">Failed to load screener data</p></div>);
  }

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-bold text-[#f0f4f0]">Stock Screener</h2>
        <p className="text-[#6b7f8e] mt-1">Filter and sort stocks by fundamentals</p>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-4">
        <div>
          <label className="text-xs text-[#6b7f8e] mb-1 block">Country</label>
          <Select value={country} onValueChange={setCountry}>
            <SelectTrigger><SelectValue placeholder="All" /></SelectTrigger>
            <SelectContent>
              {COUNTRIES.map((c) => (<SelectItem key={c.value} value={c.value}>{c.label}</SelectItem>))}
            </SelectContent>
          </Select>
        </div>
        <div>
          <label className="text-xs text-[#6b7f8e] mb-1 block">Sort By</label>
          <Select value={sortBy} onValueChange={setSortBy}>
            <SelectTrigger><SelectValue /></SelectTrigger>
            <SelectContent>
              {SORT_OPTIONS.map((s) => (<SelectItem key={s.value} value={s.value}>{s.label}</SelectItem>))}
            </SelectContent>
          </Select>
        </div>
        <div>
          <label className="text-xs text-[#6b7f8e] mb-1 block">Limit</label>
          <Select value={String(limit)} onValueChange={(v) => setLimit(Number(v))}>
            <SelectTrigger><SelectValue /></SelectTrigger>
            <SelectContent>
              {[10, 25, 50, 100].map((n) => (<SelectItem key={n} value={String(n)}>{n}</SelectItem>))}
            </SelectContent>
          </Select>
        </div>
        <div>
          <label className="text-xs text-[#6b7f8e] mb-1 block">P/E Min</label>
          <Input type="number" placeholder="Min" value={peMin} onChange={(e) => setPeMin(e.target.value)} />
        </div>
        <div>
          <label className="text-xs text-[#6b7f8e] mb-1 block">P/E Max</label>
          <Input type="number" placeholder="Max" value={peMax} onChange={(e) => setPeMax(e.target.value)} />
        </div>
        <div>
          <label className="text-xs text-[#6b7f8e] mb-1 block">Search</label>
          <Input placeholder="Ticker or name" value={globalFilter} onChange={(e) => setGlobalFilter(e.target.value)} />
        </div>
      </div>

      <div className="grid grid-cols-2 gap-4">
        <div>
          <label className="text-xs text-[#6b7f8e] mb-1 block">Market Cap Min</label>
          <Input type="number" placeholder="e.g. 1000000000" value={mcMin} onChange={(e) => setMcMin(e.target.value)} />
        </div>
        <div>
          <label className="text-xs text-[#6b7f8e] mb-1 block">Market Cap Max</label>
          <Input type="number" placeholder="e.g. 500000000000" value={mcMax} onChange={(e) => setMcMax(e.target.value)} />
        </div>
      </div>

      <div className="rounded-lg border border-[#1e2d3a]">
        {isLoading ? (
          <div className="p-8 space-y-3">
            {Array.from({ length: 5 }).map((_, i) => (<Skeleton key={i} className="h-10 w-full" />))}
          </div>
        ) : (
          <>
            <Table>
              <TableHeader>
                {table.getHeaderGroups().map((hg) => (
                  <TableRow key={hg.id}>
                    {hg.headers.map((h) => (<TableHead key={h.id}>{h.isPlaceholder ? null : flexRender(h.column.columnDef.header, h.getContext())}</TableHead>))}
                  </TableRow>
                ))}
              </TableHeader>
              <TableBody>
                {table.getRowModel().rows.length === 0 ? (
                  <TableRow><TableCell colSpan={columns.length} className="text-center text-[#6b7f8e] py-8">No results found</TableCell></TableRow>
                ) : (
                  table.getRowModel().rows.map((row) => (
                    <TableRow key={row.id}>
                      {row.getVisibleCells().map((cell) => (<TableCell key={cell.id}>{flexRender(cell.column.columnDef.cell, cell.getContext())}</TableCell>))}
                    </TableRow>
                  ))
                )}
              </TableBody>
            </Table>
            <div className="flex items-center justify-between px-4 py-3 border-t border-[#1e2d3a]">
              <span className="text-sm text-[#6b7f8e]">{table.getRowModel().rows.length} of {results.length} results</span>
              <div className="flex gap-2">
                <Button variant="outline" size="sm" onClick={() => table.previousPage()} disabled={!table.getCanPreviousPage()}>Previous</Button>
                <Button variant="outline" size="sm" onClick={() => table.nextPage()} disabled={!table.getCanNextPage()}>Next</Button>
              </div>
            </div>
          </>
        )}
      </div>
    </div>
  );
}