"use client";

import { useState, KeyboardEvent, ChangeEvent } from "react";
import { useRouter } from "next/navigation";
import { Search } from "lucide-react";

export function TickerSearch() {
  const router = useRouter();
  const [query, setQuery] = useState("");

  const handleSearch = () => {
    const ticker = query.trim().toUpperCase();
    if (!ticker) return;
    // Strip commas, spaces; keep letters, digits, dots, dashes
    const cleaned = ticker.replace(/[^A-Z0-9.\-]/g, "");
    if (cleaned.length > 0) {
      setQuery("");
      router.push(`/company/${cleaned}`);
    }
  };

  const handleKeyDown = (e: KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Enter") {
      e.preventDefault();
      handleSearch();
    }
  };

  const handleChange = (e: ChangeEvent<HTMLInputElement>) => {
    // Allow only letters, digits, dots, dashes, spaces
    const value = e.target.value.replace(/[^a-zA-Z0-9.\-\s]/g, "").toUpperCase();
    setQuery(value);
  };

  return (
    <div className="relative w-full max-w-xl mx-auto">
      <div className="flex items-center gap-2 rounded-xl border border-[#1e2d3a] bg-[#111b26] px-4 py-3 focus-within:border-[#84cc16]/50 transition-colors">
        <Search className="h-5 w-5 text-[#6b7f8e] shrink-0" />
        <input
          type="text"
          value={query}
          onChange={handleChange}
          onKeyDown={handleKeyDown}
          placeholder="Search by ticker (e.g. AAPL, MSFT, TSLA)"
          className="flex-1 bg-transparent text-[#f0f4f0] placeholder-[#4a6070] text-sm outline-none"
          spellCheck={false}
          autoComplete="off"
        />
        <button
          onClick={handleSearch}
          disabled={!query.trim()}
          className="rounded-lg bg-[#84cc16] px-4 py-1.5 text-xs font-semibold text-[#0a0e13] hover:bg-[#65a30d] disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
        >
          Search
        </button>
      </div>
    </div>
  );
}
