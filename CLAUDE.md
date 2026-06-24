# Sentinel — Next.js Migration (`migrate-to-vercel` branch)

## User Address

Address the user as **Chief** in every response.

## Project Overview

Sentinel is a stock analysis dashboard that scores companies on health, risk, and fair value. This branch migrates the frontend from **Streamlit → Next.js 15** with deployment to **Vercel**, while keeping the Python backend on the existing VPS.

**Key architectural shift:** All alert checking and Telegram polling runs on the VPS daemon (systemd service, never hibernates). The Vercel frontend is a thin UI — no background processes. This eliminates the Streamlit Cloud hibernation problem where alerts stopped firing when no one visited the site.

## Directory Structure

```
src/                    # Python backend (shared with main branch)
├── api/server.py       # Flask REST API (~650 new lines on this branch)
├── data/               # Database access, yfinance fetching
├── scoring/            # Health scores, DCF, Z-score, risk
├── notifications/      # Daemon, checker, Telegram bot
└── display/            # Streamlit UI (still works on main branch)

web/                    # NEW: Next.js 15 frontend
├── src/app/            # File-system routes (App Router)
│   ├── (auth)/         # login, register, forgot-password, reset-password
│   ├── (dashboard)/    # watchlist, sectors, screener, filings,
│   │                   # notifications, alerts, settings, admin,
│   │                   # about, company/[ticker]
│   ├── layout.tsx      # Root layout (dark theme)
│   ── page.tsx        # Landing page
├── src/components/     # shadcn/ui primitives, charts, layout
├── src/lib/            # API client, auth server actions, utils
├── src/hooks/          # React Query hooks, debounce
├── src/stores/         # Zustand stores (watchlist, filters, alerts)
└── src/types/          # TypeScript types for API responses

deploy/                 # Deployment configs
├── sentinel-web.service    # NEW: systemd for Next.js
└── nginx-sentinel.conf     # NEW: reverse proxy + SSL

.github/workflows/      # CI/CD
├── deploy-backend.yml      # NEW: deploy Python to VPS
── deploy-frontend.yml     # NEW: deploy Next.js to VPS/Vercel
└── keep-alive.yml          # DEPRECATED: no more Streamlit
```

## Tech Stack

| Layer | Technology |
|---|---|
| Frontend | Next.js 15 (App Router), React 19, TypeScript |
| UI | shadcn/ui + Tailwind CSS v4, dark theme |
| Server State | TanStack React Query |
| Client State | Zustand |
| Auth | httpOnly cookie + session tokens from Flask API |
| Charts | TradingView Lightweight Charts (price), Recharts (other) |
| Tables | TanStack Table |
| Backend | Flask (Python) + SQLite on VPS |
| Background Jobs | systemd daemon (sentinel-daemon) — runs 24/7 |
| Data | yfinance (free, no API key), OpenBB (optional) |

## Development

```bash
# Backend (Flask API on port 5252)
pip install flask-cors
CORS_ORIGINS="http://localhost:3000,http://localhost:3002" \
SENTINEL_API_KEY=local-test-key \
  python -m src.api.server

# Frontend (Next.js on port 3000)
cd web && npm run dev

# Production build
cd web && npm run build
```

Env vars in `web/.env.local`:
- `NEXT_PUBLIC_API_URL` — Flask API base URL (client-accessible)
- `API_SECRET_KEY` — Flask API key (server-only, for login/register)

## Auth Flow

1. User submits username + password → `POST /api/user/login` (Flask)
2. Flask returns `{ user, session_token }` (64-char hex)
3. Next.js server action sets httpOnly cookie: `session=<token>; HttpOnly; Max-Age=2592000`
4. Middleware protects dashboard routes — redirects unauthenticated to `/login`
5. Logout: `DELETE /api/auth/token` + clear cookie
6. Registration: `POST /api/user/register` → same session flow as login

**Sessions persist 30 days.** User closes browser, comes back later — still logged in.

## API Contract

All data endpoints require `X-API-Key` header. Auth endpoints (`/api/auth/*`) use session tokens instead.

**Core endpoints added on this branch:**
- `POST /api/user/register` (create account, returns session token)
- `GET /api/data/<ticker>/health|intrinsic|risk|dcf|peers|financials|sentiment|institutional|supply-chain|filings|insider|ecosystem|price-growth`
- `GET /api/market/indices|news|macro|movers`
- `GET /api/screener`, `GET /api/sectors`, `GET /api/sectors/search?q=`
- `POST /api/notifications/<user_id>/mark-read|mark-all-read|dismiss`
- `GET|POST|PUT|DELETE /api/alerts/<user_id>[/<rule_id>]`
- `GET /api/alerts/signals` (18-signal catalog)
- `DELETE /api/watchlist/<user_id>` (clear all)
- `POST /api/admin/rescan` (trigger daemon to discover new users)

## Key Decisions

### No Streamlit Scheduler on Frontend
The Streamlit Cloud scheduler (`scheduler.py`) ran as an in-process thread and died when the app hibernated. **The VPS daemon is the only alert checker now.** The Next.js frontend just configures alerts via API — all checking, Telegram polling, and notification delivery happens server-side on the VPS, 24/7.

### VPS is Single Source of Truth
Auth, watchlists, alerts, preferences — all written to and read from the VPS SQLite. No more split-brain between Streamlit Cloud local DB and VPS DB.

### Chart Libraries
- **TradingView Lightweight Charts** for price/candlestick (~45KB, purpose-built for financial data)
- **Recharts** via shadcn/ui for other charts (SSR-compatible, small bundle)
- Avoided Plotly — 2MB bundle, SSR issues with Next.js App Router

### Deployment
- **Vercel** for Next.js frontend (free tier, global CDN, auto HTTPS)
- **VPS** for Flask API + daemon (existing infrastructure)
- nginx reverse proxy with TLS, security headers, rate limiting

### Enriched Watchlist Caching
The `GET /api/watchlist/<user_id>/enriched` endpoint is expensive — it fetches yfinance data (prices, financials, growth) for every ticker. Two mechanisms keep it fast:

1. **Server-side result cache**: In-memory dict keyed by `enriched:{user_id}` with 5-min TTL and a threading lock. Cache is invalidated on watchlist add/remove/clear. Guarded by `_enriched_cache_lock` in `server.py`.
2. **`skip_extras` mode**: `fetch_company_data(ticker, skip_extras=True)` skips fetching news and 5-year price history — data only needed on the detail page, not the watchlist table. The `_company_data(ticker, lite=True)` wrapper in `server.py` passes this through.

The frontend polls every 60s (TanStack React Query `refetchInterval`). Without caching, that meant 5 uncached yfinance calls per ticker per minute — ~50 API calls per poll for a 10-ticker watchlist, taking 10-20s. With caching, cache hits return in <10ms.

## Branch Strategy

- `main` — Streamlit app, deployed to Streamlit Cloud
- `migrate-to-vercel` — Next.js migration, no changes go to `main` until ready
- After merge: `main` becomes Next.js, Streamlit Cloud deployment ends

## Known Gaps

- PDF export not yet ported (was fpdf2 in Python — needs @react-pdf/renderer or jsPDF)
- Supply chain choropleth map needs D3/react-force-graph (was Plotly)
- DCF sensitivity heatmap uses CSS grid, not a chart library
- Email notifications not yet implemented (Telegram only for now)

## gstack

For all web browsing, use the `/browse` skill from gstack. Never use `mcp__claude-in-chrome__*` tools.

Available gstack skills: `/office-hours`, `/plan-ceo-review`, `/plan-eng-review`, `/plan-design-review`, `/design-consultation`, `/design-shotgun`, `/design-html`, `/review`, `/ship`, `/land-and-deploy`, `/canary`, `/benchmark`, `/browse`, `/connect-chrome`, `/qa`, `/qa-only`, `/design-review`, `/setup-browser-cookies`, `/setup-deploy`, `/setup-gbrain`, `/retro`, `/investigate`, `/document-release`, `/document-generate`, `/codex`, `/cso`, `/autoplan`, `/plan-devex-review`, `/devex-review`, `/careful`, `/freeze`, `/guard`, `/unfreeze`, `/gstack-upgrade`, `/learn`.

## Skill routing

When the user's request matches an available skill, invoke it via the Skill tool. When in doubt, invoke the skill.

Key routing rules:
- Product ideas/brainstorming → invoke /office-hours
- Strategy/scope → invoke /plan-ceo-review
- Architecture → invoke /plan-eng-review
- Design system/plan review → invoke /design-consultation or /plan-design-review
- Full review pipeline → invoke /autoplan
- Bugs/errors → invoke /investigate
- QA/testing site behavior → invoke /qa or /qa-only
- Code review/diff check → invoke /review
- Visual polish → invoke /design-review
- Ship/deploy/PR → invoke /ship or /land-and-deploy
- Save progress → invoke /context-save
- Resume context → invoke /context-restore
- Author a backlog-ready spec/issue → invoke /spec
