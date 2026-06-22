const API_KEY = process.env.NEXT_PUBLIC_API_KEY || "";

export interface FetchOptions extends RequestInit {
  params?: Record<string, string | number | boolean>;
}

// Market mover shape
export interface Mover {
  ticker: string;
  name: string;
  price: number;
  change_pct: number;
  direction: "up" | "down";
  volume: number;
}

export interface MacroIndicator {
  value: number;
  label: string;
  verdict: string;
  color: string;
  detail: string;
}

export interface MacroIndicators {
  vix?: MacroIndicator;
  sp500?: MacroIndicator;
  yield_curve?: MacroIndicator;
  credit?: MacroIndicator;
  dollar?: MacroIndicator;
}

async function fetchApi<T>(path: string, options: FetchOptions = {}): Promise<T> {
  const { params, ...rest } = options;

  const url = new URL(path.startsWith("http") ? path : path, window.location.origin);
  if (params) {
    Object.entries(params).forEach(([key, value]) => {
      url.searchParams.append(key, String(value));
    });
  }

  const response = await fetch(url.toString(), {
    ...rest,
    headers: {
      "Content-Type": "application/json",
      ...(API_KEY ? { "X-API-Key": API_KEY } : {}),
      ...rest.headers,
    },
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ error: response.statusText }));
    throw new Error(error.error || `API error: ${response.status}`);
  }

  return response.json();
}

export const api = {
  // Generic helpers for flexible API calls
  get: <T>(path: string, options?: FetchOptions) => fetchApi<T>(path, { ...options, method: "GET" }),
  post: <T>(path: string, body?: Record<string, unknown>) =>
    fetchApi<T>(path, { method: "POST", body: JSON.stringify(body ?? {}) }),
  put: <T>(path: string, body?: Record<string, unknown>) =>
    fetchApi<T>(path, { method: "PUT", body: JSON.stringify(body ?? {}) }),
  delete: <T>(path: string) => fetchApi<T>(path, { method: "DELETE" }),

  // Market
  getIndices: () => fetchApi<{ indices: { name: string; value: number; change: number; change_pct: number }[] }>("/api/market/indices"),
  getMacro: () => fetchApi<MacroIndicators>("/api/market/macro"),
  getNews: (limit = 5) => fetchApi<{ news: unknown[] }>("/api/market/news", { params: { limit } }),
  getMovers: (topN = 10) => fetchApi<{ gainers: Mover[]; losers: Mover[] }>(`/api/market/movers`, { params: { top_n: topN } }),

  // Watchlist
  getWatchlist: (userId: number) => fetchApi<{ tickers: string[] }>(`/api/watchlist/${userId}`),
  getEnrichedWatchlist: (userId: number) => fetchApi<{ user_id: number; items: Array<{ ticker: string; name: string; sector: string; price: number; change: number; change_pct: number; healthScore: number; verdict: string; riskLabel: string; growth3m: number | null; growth6m: number | null; growth12m: number | null; error?: boolean }> }>(`/api/watchlist/${userId}/enriched`),
  addToWatchlist: (userId: number, ticker: string) => fetchApi<{ ok: boolean }>("/api/watchlist", { method: "POST", body: JSON.stringify({ user_id: userId, ticker }) }),
  removeFromWatchlist: (userId: number, ticker: string) => fetchApi<{ ok: boolean }>(`/api/watchlist/${userId}/${ticker}`, { method: "DELETE" }),

  // Company Data
  getHealth: (ticker: string) => fetchApi<Record<string, unknown>>(`/api/data/${ticker}/health`),
  getIntrinsic: (ticker: string) => fetchApi<Record<string, unknown>>(`/api/data/${ticker}/intrinsic`),
  getRisk: (ticker: string) => fetchApi<Record<string, unknown>>(`/api/data/${ticker}/risk`),
  getFinancials: (ticker: string) => fetchApi<Record<string, unknown>>(`/api/data/${ticker}/financials`),
  getDcf: (ticker: string, params?: {
    revenue_growth_5yr?: number;
    terminal_growth?: number;
    discount_rate?: number;
    margin_improvement?: number;
  }) => fetchApi<Record<string, unknown>>(`/api/data/${ticker}/dcf`, { params: params as Record<string, string | number | boolean> }),
  getPriceGrowth: (ticker: string) => fetchApi<Record<string, unknown>>(`/api/data/${ticker}/price-growth`),
  getPriceHistory: (ticker: string, period = "1y") =>
    fetchApi<{ candles: { date: string; open: number; high: number; low: number; close: number; volume: number }[] }>(
      `/api/data/${ticker}/price-history`,
      { params: { period } },
    ),
  getPeers: (ticker: string) => fetchApi<Record<string, unknown>>(`/api/data/${ticker}/peers`),
  getSentiment: (ticker: string) => fetchApi<Record<string, unknown>>(`/api/data/${ticker}/sentiment`),
  getInstitutional: (ticker: string) => fetchApi<Record<string, unknown>>(`/api/data/${ticker}/institutional`),
  getFilings: (ticker: string) => fetchApi<Record<string, unknown>>(`/api/data/${ticker}/filings`),
  getInsider: (ticker: string) => fetchApi<Record<string, unknown>>(`/api/data/${ticker}/insider`),
  getEcosystem: (ticker: string) => fetchApi<Record<string, unknown>>(`/api/data/${ticker}/ecosystem`),
  getSupplyChain: (ticker: string) => fetchApi<Record<string, unknown>>(`/api/data/${ticker}/supply-chain`),

  // User & Auth
  /**
   * Fetch the current user from session. Returns null (not throw) on 401
   * so that unauthenticated users don't fill the console with spurious errors.
   */
  getMe: async () => {
    const res = await fetch("/api/auth/me", {
      headers: { "Content-Type": "application/json" },
    });
    if (res.status === 401) return null;
    if (!res.ok) {
      const err = await res.json().catch(() => ({ error: res.statusText }));
      throw new Error(
        (err as { error?: string }).error || `API error: ${res.status}`,
      );
    }
    const data = await res.json();
    return (data.user ?? data) as import("@/types/api").User;
  },
  logout: () => fetchApi<Record<string, unknown>>("/api/auth/token", { method: "DELETE" }),

  // Preferences
  getPreferences: (userId: number) => fetchApi<Record<string, unknown>>(`/api/preferences/${userId}`),
  setPreferences: (userId: number, prefs: Record<string, unknown>) =>
    fetchApi<{ ok: boolean }>(`/api/preferences/${userId}`, { method: "POST", body: JSON.stringify(prefs) }),

  // Notifications
  getNotifications: (userId: number, limit = 10, unreadOnly = false) =>
    fetchApi<Record<string, unknown>>(`/api/notifications/${userId}`, { params: { limit, unread_only: unreadOnly } }),
  getUnreadCount: (userId: number) => fetchApi<{ count: number }>(`/api/notifications/${userId}/unread-count`),

  // Telegram
  getBotTokens: () => fetchApi<Record<string, unknown>>("/api/bot-tokens"),
};

export default api;
