"use client";

import { useState, useMemo, useEffect, useRef } from "react";
import { useQuery } from "@tanstack/react-query";
import { flexRender, getCoreRowModel, getSortedRowModel, getPaginationRowModel, useReactTable, type SortingState, type ColumnDef, type Column } from "@tanstack/react-table";
import { ArrowUpDown, Search as SearchIcon, ArrowUp, ArrowDown } from "lucide-react";
import Link from "next/link";
import { api } from "@/lib/api-client";
import { useDebounce } from "@/hooks/use-debounce";
import { formatCurrency, formatPct, getHealthBg } from "@/lib/utils";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Skeleton } from "@/components/ui/skeleton";

interface SectorResult { ticker: string; name: string; sector: string; industry: string; price: number; marketCap: number; pe: number | null; change: number; healthScore: number; }

function cell(info: { getValue: () => unknown }): string { return info.getValue() as string; }
function cellNum(info: { getValue: () => unknown }): number { return info.getValue() as number; }

export default function SectorsPage() {
  const [search, setSearch] = useState("");
  const [selectedSector, setSelectedSector] = useState("");
  const [selectedIndustry, setSelectedIndustry] = useState("");
  const [sorting, setSorting] = useState<SortingState>([]);
  const debouncedSearch = useDebounce(search, 400);
  const hasAutoSelected = useRef(false);

  const { data: sectorsData } = useQuery({ queryKey: ["sectors"], queryFn: () => api.get<{ sectors: string[] }>("/api/sectors") });
  const sectorList: string[] = useMemo(() => sectorsData?.sectors ?? [], [sectorsData]);

  useEffect(() => {
    if (!hasAutoSelected.current && sectorList.length > 0) {
      setSelectedSector(sectorList[0]);
      hasAutoSelected.current = true;
    }
  }, [sectorList]);

  const { data, isLoading } = useQuery({
    queryKey: ["sectors-search", debouncedSearch, selectedSector, selectedIndustry],
    queryFn: () => {
      const params: Record<string, string> = {};
      if (debouncedSearch) params.q = debouncedSearch;
      if (selectedSector) params.sector = selectedSector;
      if (selectedIndustry) params.industry = selectedIndustry;
      return api.get<{ results: SectorResult[] }>("/api/sectors/search", { params });
    },
  });

  const results = data?.results ?? [];

  useEffect(() => { setSelectedIndustry(""); }, [selectedSector]);

  const columns: ColumnDef<SectorResult>[] = useMemo(() => [
    {
      accessorKey: "ticker",
      header: "Ticker",
      cell: (info) => (<Link href={"/company/" + cell(info)} className="text-[#84cc16] hover:text-[#65a30d] font-mono font-medium transition-colors">{cell(info)}</Link>),
    },
    { accessorKey: "name", header: "Company", cell: (info) => <span className="text-[#c8d8e4]">{cell(info)}</span> },
    { accessorKey: "sector", header: "Sector", cell: (info) => <Badge variant="secondary">{cell(info)}</Badge> },
    { accessorKey: "industry", header: "Industry", cell: (info) => <span className="text-[#6b7f8e] text-sm">{cell(info)}</span> },
    {
      accessorKey: "price",
      header: (h) => (<button onClick={() => (h.column as Column<SectorResult>).toggleSorting()} className="flex items-center gap-1">Price <ArrowUpDown className="h-3 w-3" /></button>),
      cell: (info) => formatCurrency(cellNum(info)),
    },
    {
      accessorKey: "marketCap",
      header: (h) => (<button onClick={() => (h.column as Column<SectorResult>).toggleSorting()} className="flex items-center gap-1">Mkt Cap <ArrowUpDown className="h-3 w-3" /></button>),
      cell: (info) => formatCurrency(cellNum(info)),
    },
    { accessorKey: "pe", header: "P/E", cell: (info) => { const v = cellNum(info); return v != null ? v.toFixed(2) : "N/A"; } },
    {
      accessorKey: "change",
      header: (h) => (<button onClick={() => (h.column as Column<SectorResult>).toggleSorting()} className="flex items-center gap-1">Change <ArrowUpDown className="h-3 w-3" /></button>),
      cell: (info) => { const v = cellNum(info); const c = v >= 0 ? "text-[#84cc16]" : "text-red-400"; const Ic = v >= 0 ? ArrowUp : ArrowDown; return (<span className={"flex items-center gap-1 " + c}><Ic className="h-3 w-3" />{formatPct(v)}</span>); },
    },
    {
      accessorKey: "healthScore",
      header: (h) => (<button onClick={() => (h.column as Column<SectorResult>).toggleSorting()} className="flex items-center gap-1">Health <ArrowUpDown className="h-3 w-3" /></button>),
      cell: (info) => <Badge className={getHealthBg(cellNum(info))}>{cellNum(info)}</Badge>,
    },
    { id: "actions", header: "", cell: ({ row }) => (<Link href={"/company/" + row.original.ticker}><Button size="sm" variant="outline" className="text-xs">Analyze</Button></Link>) },
  ], []);

  const table = useReactTable({ data: results, columns, state: { sorting }, onSortingChange: setSorting, getCoreRowModel: getCoreRowModel(), getSortedRowModel: getSortedRowModel(), getPaginationRowModel: getPaginationRowModel(), initialState: { pagination: { pageSize: 25 } } });

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-bold text-[#f0f4f0]">Sector Search</h2>
        <p className="text-[#6b7f8e] mt-1">Explore companies by sector and industry</p>
      </div>
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <div className="md:col-span-2">
          <label className="text-xs text-[#6b7f8e] mb-1 block">Search</label>
          <div className="relative">
            <SearchIcon className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-[#6b7f8e]" />
            <Input placeholder="Search sectors, industries, or companies..." value={search} onChange={(e) => setSearch(e.target.value)} className="pl-9" />
          </div>
        </div>
        <div>
          <label className="text-xs text-[#6b7f8e] mb-1 block">Sector</label>
          <Select value={selectedSector} onValueChange={setSelectedSector}>
            <SelectTrigger><SelectValue placeholder="All sectors" /></SelectTrigger>
            <SelectContent>
              <SelectItem value="">All Sectors</SelectItem>
              {sectorList.map((s) => (<SelectItem key={s} value={s}>{s}</SelectItem>))}
            </SelectContent>
          </Select>
        </div>
        <div>
          <label className="text-xs text-[#6b7f8e] mb-1 block">Industry</label>
          <Select value={selectedIndustry} onValueChange={setSelectedIndustry}>
            <SelectTrigger><SelectValue placeholder="All industries" /></SelectTrigger>
            <SelectContent>
              <SelectItem value="">All Industries</SelectItem>
            </SelectContent>
          </Select>
        </div>
      </div>
      <div className="rounded-lg border border-[#1e2d3a]">
        {isLoading ? (<div className="p-8 space-y-3">{Array.from({ length: 5 }).map((_, i) => (<Skeleton key={i} className="h-10 w-full" />))}</div>) : (<>
          <Table>
            <TableHeader>{table.getHeaderGroups().map((hg) => (<TableRow key={hg.id}>{hg.headers.map((h) => (<TableHead key={h.id}>{h.isPlaceholder ? null : flexRender(h.column.columnDef.header, h.getContext())}</TableHead>))}</TableRow>))}</TableHeader>
            <TableBody>{table.getRowModel().rows.length === 0 ? (<TableRow><TableCell colSpan={columns.length} className="text-center text-[#6b7f8e] py-8">No results found</TableCell></TableRow>) : table.getRowModel().rows.map((row) => (<TableRow key={row.id}>{row.getVisibleCells().map((c) => (<TableCell key={c.id}>{flexRender(c.column.columnDef.cell, c.getContext())}</TableCell>))}</TableRow>))}</TableBody>
          </Table>
          <div className="flex items-center justify-between px-4 py-3 border-t border-[#1e2d3a]">
            <span className="text-sm text-[#6b7f8e]">{table.getRowModel().rows.length} results</span>
            <div className="flex gap-2">
              <Button variant="outline" size="sm" onClick={() => table.previousPage()} disabled={!table.getCanPreviousPage()}>Previous</Button>
              <Button variant="outline" size="sm" onClick={() => table.nextPage()} disabled={!table.getCanNextPage()}>Next</Button>
            </div>
          </div>
        </>)}
      </div>
    </div>
  );
}