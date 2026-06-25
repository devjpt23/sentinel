# Finnhub REST Integration Design

## Status: DRAFT

## Motivation

The dashboard loads company data (prices, names, financials, scores) through
`fetch_company_data()` which relies entirely on yfinance. Each ticker takes
2-5 seconds because yfinance's `.info` endpoint is a slow aggregate of dozens
of underlying API calls. With Finnhub's REST API already available (we use
the WebSocket for alerts), we can serve the majority of display data from
Finnhub's fast REST endpoints and restrict yfinance to the financial
statements that the scoring engine requires.

## Goals

- Reduce enriched watchlist load time from 6s+ to ~1-2s
- Keep Finnhub free-tier calls under 60/min with caching
- Zero changes to the frontend — API contract stays identical
- Graceful degradation: yfinance fills gaps when Finnhub returns null or
  hits rate limits

## Non-Goals

- Replacing yfinance financial statements (balance sheet, income, cash flow
  statement — these are needed for scoring and unavailable on Finnhub free)
- Replacing price history (growth calculation, charts — yfinance only)
- Changing the frontend data model

## Architecture

### New File: `src/data/finnhub_rest.py`

A `FinnhubRestClient` class wrapping three Finnhub REST API endpoints:

| Method | Endpoint | Returns |
|--------|----------|---------|
| `get_quote(ticker)` | `GET /api/v1/quote` | `{c, d, dp, h, l, o, pc}` |
| `get_profile(ticker)` | `GET /api/v1/stock/profile2` | `{name, sector, industry, logo, marketCap, shareOutstanding, employees}` |
| `get_basic_financials(ticker)` | `GET /api/v1/stock/basic-financials` | `{metric: {pe, epsAnnual, beta, dividendYield, ...}}` |

Key characteristics:

- **30s in-memory cache** per endpoint+ticker — `cache: Dict[str, tuple[float, dict]]`
- **Rate-limit guard**: tracks recent call count; if approaching 60/min,
  falls back to returning `None` (cache miss = yfinance fallback)
- **No API key = all None**: same pattern as the WebSocket feed — graceful
  no-op when `FINNHUB_API_KEY` is not set
- **Simple field extraction**: each method returns a flat dict with only the
  fields the fetcher needs

### Modified: `src/data/fetcher.py`

`fetch_company_data()` gets a fast path when `skip_extras=True` (watchlist
mode). When Finnhub is available and configured:

- **Skip yfinance `.info` entirely** — the heaviest call (2-5s per ticker)
- Fetch quote + profile from Finnhub REST (100-200ms total)
- Only hit yfinance for financial statements when scoring data is needed
  (company detail page, not watchlist)

When `skip_extras=False` (company detail page), both sources run:
Finnhub for display data, yfinance financial statements for scoring.

```
skip_extras=True (watchlist):
  Finnhub quote + profile → merge → return (~200ms total)
  No yfinance call at all

skip_extras=False (detail page):
  Finnhub quote + profile                 ─┐
    (display fields, fast)                  ├── merge → full data dict
  yfinance financial statements only       ─┘
    (scoring needs: balance, income, cash)
```

Concretely, a new function `_enrich_with_finnhub(data: dict, ticker: str)`
runs after `_fetch_company_data_yf()` and overwrites certain fields with
Finnhub values:

```python
def _apply_finnhub_data(data: dict, ticker: str) -> dict:
    """Overwrite display fields in *data* with Finnhub values where available.
    
    Only overwrites keys when Finnhub returns a non-null value. yfinance
    values serve as fallback for any null fields.
    """
    client = _get_finnhub_client()
    if not client:
        return data

    quote = client.get_quote(ticker)
    if quote:
        for k, v in {"price": "c", "previous_close": "pc",
                      "change": "d", "change_pct": "dp",
                      "day_high": "h", "day_low": "l", "open": "o"}.items():
            if quote.get(v) is not None:
                data["market"][k] = quote[v]

    profile = client.get_profile(ticker)
    if profile:
        for k, v in {"name": "name", "sector": "sector",
                      "industry": "industry"}.items():
            if profile.get(v) is not None:
                data["company"][k] = profile[v]
        for k, v in {"employees": "employees", "beta": "beta",
                      "market_cap": "marketCap",
                      "shares_outstanding": "shareOutstanding"}.items():
            if profile.get(v) is not None:
                data["market"][k] = profile[v]

    financials = client.get_basic_financials(ticker)
    if financials:
        for k, v in {"pe_ttm": "pe", "eps_ttm": "epsAnnual",
                      "pb_ratio": "pb"}.items():
            if financials.get(v) is not None:
                data["valuation"][k] = financials[v]

    return data
```

### Important: No Frontend Changes

The API response shape is unchanged. The frontend gets the same JSON. The
only difference is that data arrives faster (Finnhub REST ~200ms vs yfinance
~3s).

## Data Flow

```
Request to /api/watchlist/<id>/enriched
         │
    ┌────▼────┐
    │  Cache  │── hit ──→ return cached response (~10ms)
    │  hit?   │
    └────┬────┘
         │ miss
         ▼
    Parallel fetch for each ticker:
    ┌─────────────────────────────────────┐
    │ Finnhub: get_quote + get_profile    │ ← 100-200ms
    │   (cheap, fast, cached 30s)        │
    │                                     │
    │ yfinance: only financial statements │ ← 1-2s (lighter than .info)
    │   for health/risk scoring           │
    │                                     │
    │ fetch_price_growth (yfinance)       │ ← cached 5min, only if needed
    └─────────────────────────────────────┘
         │
         ▼
    Merge → cache 5min → return
```

Since Finnhub fills most display fields, the yfinance `.info` call can be
replaced with a targeted financial-statements-only fetch when scoring data
is needed (enriched watchlist skips this with `skip_extras`, company detail
page needs it for scores).

## Caching Strategy

| Cache | TTL | Scope | Purpose |
|-------|-----|-------|---------|
| Finnhub in-memory | 30s | Per endpoint+ticker | Stay under 60 calls/min |
| Enriched watchlist | 5min | Per user | Avoid recomputing scores |
| Finnhub quote | 30s | Per ticker | Fresh prices vs rate limit |

## Rate Limit Safety

Finnhub free: 60 REST calls/minute. Worst case: 10-ticker watchlist × 3
endpoints = 30 calls. With 30s cache, the second load within 30s is 0
calls. Safety mechanisms:

1. **30s cache** — ensures repeated loads within 30s don't count
2. **Rate-limit tracking** — if approaching 55 calls in the current minute,
   return `None` and let yfinance fill
3. **Graceful degredation** — Finnhub null/None → yfinance value is
   preserved in the merged dict

## Error Handling

- Finnhub endpoint failure → log WARNING, continue with yfinance data
- Rate limit (HTTP 429) → mark minutely counter full, fall back
- No API key env var → `FinnhubRestClient` is None, `_enrich_with_finnhub`
  is a no-op
- JSON parse errors → log WARNING, skip that endpoint's update

## Testing

- `tests/test_finnhub_rest.py` — 8-10 unit tests:
  - `test_get_quote_parsing` — valid JSON parsed correctly
  - `test_get_profile_parsing`
  - `test_get_basic_financials_parsing`
  - `test_cache_hit` — 30s cache returns cached value
  - `test_cache_expiry` — stale cache refetches
  - `test_rate_limit_tracking` — approaching 60/min returns None
  - `test_no_api_key` — safe no-op
  - `test_malformed_response` — graceful degradation
  - `test_enrich_merges_correctly` — `_enrich_with_finnhub` overwrites only
    specified fields, leaves others intact
- Existing fetcher tests must continue to pass (no breaking changes)

## Edge Cases

- Finnhub `get_quote("")` → graceful empty response
- Finnhub profile returns null for a field → yfinance value preserved
- All 3 endpoints returning None → `_enrich_with_finnhub` is a no-op,
  yfinance data serves as-is
- Consecutive rate-limit hits → FinnhubClient enters "degraded" state for
  the remainder of the minute, all calls return None
- Finnhub returns stale data (e.g., pre-market) → we still use it; it's
  fresher than yfinance's cache and the frontend handles staleness display
