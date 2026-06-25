# Sentinel

**Fundamental stock analysis -- plain English, not jargon.**

Sentinel scores any publicly traded company on financial health, price fairness, intrinsic value, and risk. Type a ticker, get a clear verdict with explanations that don't assume a finance degree.

![Python](https://img.shields.io/badge/python-%3E%3D3.10-blue)
![Next.js](https://img.shields.io/badge/next.js-15-black)
![License](https://img.shields.io/badge/license-MIT-green)

---

## Why Sentinel

Most stock analysis tools overwhelm you with 50+ metrics and jargon like "EV/EBITDA multiple expansion." Sentinel answers the three questions that matter for any stock:

1. **Is this a good company?** -- Health Score
2. **Is the price fair?** -- Price vs. Peers & Intrinsic Worth
3. **What could go wrong?** -- Risk Assessment & Red Flags

Every number comes with a plain-English explanation. No finance degree required.

---

## Architecture

Sentinel has two deployment modes:

| Mode | Frontend | Backend | Deployed To |
|---|---|---|---|
| **Current** | Next.js 15 (TypeScript) | Flask REST API | Vercel + VPS |
| **Legacy** | Streamlit (Python) | In-process | Streamlit Cloud |

This branch (`migrate-to-vercel`) runs the current architecture: a Flask API on your VPS serves data to a Next.js frontend deployable to Vercel or the same VPS. Background alert checking and Telegram polling run as a systemd daemon on the VPS -- the frontend is purely a UI layer.

```
┌─────────────┐     ┌───────────────┐     ┌─────────────┐
│  Browser     │────▶│  Next.js 15   │────▶│  Flask API  │
│  (Vercel)    │     │  (App Router) │     │  (VPS:5252) │
└─────────────┘     └───────────────┘     └──────┬──────┘
                                                  │
                                        ┌─────────▼────────┐
                                        │  SQLite (VPS)    │
                                        │  yfinance / OpenBB│
                                        └──────────────────┘

┌────────────────────────────────────────┐
│  systemd Daemon (VPS, 24/7)            │
│  ├── Alert checker (custom rules)      │
│  ├── Telegram bot (user-owned tokens)  │
│  └── Push notification sender          │
└────────────────────────────────────────┘
```

---

## Features

### Stock Analysis
- **Health Score** -- Piotroski F-Score (0-9) mapped to a 0-100 composite of profitability, leverage, and operating efficiency
- **Price vs Peers** -- Compare valuation multiples against industry peers
- **Intrinsic Worth** -- Graham Number, DCF valuation, and FCF yield analysis
- **Risk Assessment** -- Altman Z-Score bankruptcy prediction, automated red flag detection (negative earnings, debt exceeding cash, declining revenue, extreme valuations, negative FCF)
- **Narrative Summary** -- One-paragraph plain-English explanation of every stock

### Dashboard
- **Company Detail** -- Price chart, financial statements, insider activity, institutional holders, news sentiment, peer comparison, supply chain relationships, SEC filings
- **Watchlist** -- Saved tickers with live health scores, auto-refreshing price marquee
- **Sector Browser** -- Discover stocks by sector with market cap and health filtering
- **Screener** -- Multi-criteria stock screening across financial metrics
- **Notifications** -- Browser push, Telegram, and in-app notification history ([mobile setup guide](docs/mobile-user-guide.md))
- **Custom Alerts** -- Rule-based alerts triggered by scoring thresholds, price moves, or volume

### Market Data
- Major indices (S&P 500, DJIA, NASDAQ, VIX) and daily movers
- Macro dashboard (yield curve, credit spreads, dollar strength)
- News sentiment with bullish/bearish/neutral classification

### Telegram Bot
Full-featured bot for on-the-go access. Each user brings their own bot token -- no shared infrastructure. See [Telegram Bot Commands](#telegram-bot-commands).

---

## Tech Stack

| Layer | Technology |
|---|---|
| **Frontend** | Next.js 15 (App Router), React 19, TypeScript |
| **UI** | shadcn/ui + Tailwind CSS v4, dark theme |
| **Server State** | TanStack React Query |
| **Client State** | Zustand |
| **Auth** | httpOnly cookie + session tokens |
| **Charts** | TradingView Lightweight Charts (price), Recharts (other) |
| **Tables** | TanStack Table |
| **Backend** | Flask (Python 3.10+) + SQLite |
| **Market Data** | yfinance (free, no API key), OpenBB (optional) |
| **Background Jobs** | systemd daemon (`sentinel-daemon`) |
| **Notifications** | Telegram bot + Browser Push API |
| **Testing** | Vitest (frontend), pytest (backend) |
| **CI/CD** | GitHub Actions |

---

## Project Structure

```
├── src/                          # Python backend
│   ├── api/server.py             # Flask REST API (port 5252)
│   ├── data/                     # Data access layer
│   │   ├── fetcher.py            # yfinance data fetching & enrichment
│   │   ├── auth_db.py            # User authentication (SQLite)
│   │   ├── watchlist_db.py       # Watchlist persistence
│   │   ├── notification_db.py    # Notification storage
│   │   └── sector_universe.py    # Sector/industry classifications
│   ├── scoring/                  # Scoring engines
│   │   ├── health.py             # F-Score + composite Health Score (0-100)
│   │   ├── zscore.py             # Altman Z-Score bankruptcy prediction
│   │   ├── valuation.py          # Price vs peers comparison
│   │   ├── intrinsic.py          # Graham Number, DCF, FCF yield
│   │   ├── risk.py               # Red flag detection
│   │   └── dcf.py                # Discounted cash flow model
│   ├── notifications/            # Background processing
│   │   ├── daemon.py             # systemd service (24/7 alert checking)
│   │   ├── checker.py            # Custom alert rule evaluation
│   │   ├── telegram_bot.py       # Telegram bot interface
│   │   └── push_sender.py        # Browser push delivery (Web Push API)
│   └── cli/                      # CLI entry points
├── web/                          # Next.js frontend
│   ├── src/
│   │   ├── app/                  # App Router (file-system routes)
│   │   │   ├── (auth)/           # Login, register, forgot/reset password
│   │   │   ├── (dashboard)/      # Watchlist, sectors, screener, company/[ticker], etc.
│   │   │   ├── api/              # Next.js API route handlers (proxy, auth, push)
│   │   │   ├── layout.tsx        # Root layout (dark theme)
│   │   │   └── page.tsx          # Landing page
│   │   ├── components/           # React components
│   │   │   ├── ui/               # shadcn/ui primitives (button, card, dialog, etc.)
│   │   │   ├── charts/           # PriceChart, PeerScatter, DonutChart, SectorPie
│   │   │   ├── layout/           # Sidebar, top nav, price marquee
│   │   │   ├── shared/           # HealthCard, MetricCard, ScoreBadge, VerdictBadge
│   │   │   └── company/          # Company detail components
│   │   ├── lib/                  # API client, auth utilities, constants
│   │   ├── hooks/                # React Query hooks (use-company-data, use-watchlist, etc.)
│   │   ├── stores/               # Zustand stores (watchlist, filters, alerts)
│   │   └── types/                # TypeScript type definitions
│   ├── middleware.ts             # Auth protection for dashboard routes
│   └── next.config.ts            # Next.js configuration
├── deploy/                       # Production deployment configs
│   ├── sentinel-api.service      # systemd unit for Flask API
│   ├── sentinel-daemon.service   # systemd unit for background daemon
│   ├── sentinel-web.service      # systemd unit for Next.js (VPS mode)
│   ├── nginx-sentinel.conf       # nginx reverse proxy + TLS
│   ├── install-daemon.sh         # First-time deployment script
│   └── update-daemon.sh          # Update deployment script
└── .github/workflows/            # CI/CD pipelines
    ├── deploy-backend.yml        # Flask API -> VPS
    └── deploy-frontend.yml       # Next.js -> VPS or Vercel
```

---

## Quick Start (Development)

### Prerequisites

- Python 3.10+
- Node.js 22+
- npm

### Backend (Flask API)

```bash
pip install flask-cors
CORS_ORIGINS="http://localhost:3000" \
SENTINEL_API_KEY=local-dev-key \
  python -m src.api.server
```

The API starts on port 5252.

### Frontend (Next.js)

```bash
cd web
cp .env.local.example .env.local   # edit API URL and key
npm install
npm run dev
```

Open http://localhost:3000 in your browser. Register an account, then type a ticker (e.g., `NVDA`, `AAPL`) in the search bar.

### Environment Variables

File: `web/.env.local`

| Variable | Purpose |
|---|---|
| `NEXT_PUBLIC_API_URL` | Flask API base URL (client-accessible) |
| `API_SECRET_KEY` | Flask API key (server-only, for login/register) |

---

## Auth Flow

1. User submits username + password -> `POST /api/user/login` (Flask)
2. Flask returns `{ user, session_token }` (64-char hex)
3. Next.js server action sets httpOnly cookie: `session=<token>; HttpOnly; Max-Age=2592000`
4. [Middleware](web/middleware.ts) protects dashboard routes -- redirects unauthenticated to `/login`
5. Logout: `DELETE /api/auth/token` + clear cookie

Sessions persist 30 days. Closing and reopening the browser keeps the session active.

---

## API Overview

The Flask API runs on port 5252. Data endpoints require `X-API-Key` header. Auth endpoints use session tokens.

### Authentication

| Method | Endpoint | Purpose |
|---|---|---|
| POST | `/api/user/register` | Create account, returns session token |
| POST | `/api/user/login` | Login, returns session + user data |
| DELETE | `/api/auth/token` | Logout (invalidate session) |

### Company Data

| Method | Endpoint | Returns |
|---|---|---|
| GET | `/api/data/<ticker>/health` | Health score with F-Score breakdown |
| GET | `/api/data/<ticker>/intrinsic` | Graham Number, DCF, FCF yield |
| GET | `/api/data/<ticker>/risk` | Risk score + red flag list |
| GET | `/api/data/<ticker>/dcf` | Full DCF valuation model |
| GET | `/api/data/<ticker>/peers` | Peer comparison table |
| GET | `/api/data/<ticker>/financials` | Income statement, balance sheet, cash flow |
| GET | `/api/data/<ticker>/sentiment` | News headlines with sentiment labels |
| GET | `/api/data/<ticker>/institutional` | Top institutional holders |
| GET | `/api/data/<ticker>/insider` | Recent insider transactions |
| GET | `/api/data/<ticker>/filings` | SEC filing metadata |
| GET | `/api/data/<ticker>/price-growth` | Multi-period price performance |

### Market

| Method | Endpoint | Returns |
|---|---|---|
| GET | `/api/market/indices` | Major index levels (S&P 500, DJIA, NASDAQ, VIX) |
| GET | `/api/market/news` | Market-wide news headlines |
| GET | `/api/market/macro` | Macro dashboard data |
| GET | `/api/market/movers` | Top daily gainers and losers |

### Watchlist & Alerts

| Method | Endpoint | Purpose |
|---|---|---|
| GET | `/api/watchlist/<user_id>` | List saved tickers |
| POST | `/api/watchlist/<user_id>` | Add ticker to watchlist |
| DELETE | `/api/watchlist/<user_id>/<ticker>` | Remove a ticker |
| DELETE | `/api/watchlist/<user_id>` | Clear entire watchlist |
| GET | `/api/watchlist/<user_id>/enriched` | Watchlist with full scores (cached, 5-min TTL) |
| GET | `/api/alerts/<user_id>` | List alert rules |
| POST | `/api/alerts/<user_id>` | Create alert rule |
| PUT | `/api/alerts/<user_id>/<rule_id>` | Update alert rule |
| DELETE | `/api/alerts/<user_id>/<rule_id>` | Delete alert rule |
| GET | `/api/alerts/signals` | 18-signal catalog for rule conditions |

### Notifications

| Method | Endpoint | Purpose |
|---|---|---|
| GET | `/api/notifications/<user_id>` | Notification history |
| POST | `/api/notifications/<user_id>/mark-read` | Mark single as read |
| POST | `/api/notifications/<user_id>/mark-all-read` | Mark all as read |
| POST | `/api/notifications/<user_id>/dismiss` | Dismiss notification |

### Other

| Method | Endpoint | Purpose |
|---|---|---|
| GET | `/api/screener` | Multi-criteria stock screener |
| GET | `/api/sectors` | All sector classifications |
| GET | `/api/sectors/search?q=` | Search sectors by name |
| POST | `/api/admin/rescan` | Trigger daemon user discovery |

---

## Telegram Bot

Each user brings their own bot token (created via [@BotFather](https://t.me/BotFather)). No shared infrastructure.

### Setup

1. Create a bot via [@BotFather](https://t.me/BotFather) on Telegram
2. Save the token in Sentinel **Settings** page
3. Send any message to your bot -- it auto-links your chat to your Sentinel account

### Commands

| Category | Command | Description |
|---|---|---|
| **Account** | `/start` | Connect Telegram + welcome summary |
| | `/link <username>` | Link to existing Sentinel account |
| **Watchlist** | `/watchlist` | View saved tickers with price and growth |
| | `/add <TICKER>` | Add ticker to watchlist |
| | `/remove <TICKER>` | Remove ticker from watchlist |
| **Stock Info** | `/status` | Full watchlist price growth summary (3/6/12 month) |
| | `/score <TICKER>` | Complete health report |
| | `/price <TICKER>` | 3/6/12 month price growth |
| | `/news <TICKER>` | Recent headlines |
| **Market** | `/market` | Top movers + major indices |
| | `/macro` | VIX, S&P trend, yield curve, credit, dollar |
| **Notifications** | `/alerts` | View recent notifications (unread first) |
| | `/check <TICKER>` | Force immediate re-check |
| | `/interval <hours>` | Set check frequency (1-24h) |
| **Help** | `/help` | Show all commands |

### Example Flow

```
/start         ->  Welcome message + watchlist summary
/score NVDA    ->  Full health report for NVIDIA
/add MSFT      ->  Added MSFT to watchlist
/macro         ->  VIX, S&P 500 trend, yield curve, etc.
/interval 6    ->  Check every 6 hours instead of default
```

---

## Deployment

### VPS (self-hosted)

The Flask API and daemon run on a VPS behind nginx reverse proxy with TLS.

```bash
# First-time setup
./deploy/install-daemon.sh
sudo systemctl enable --now sentinel-api sentinel-daemon

# Frontend (VPS mode)
sudo systemctl enable --now sentinel-web
```

### Vercel (frontend only)

```bash
cd web
npx vercel --prod
```

CI/CD via GitHub Actions: pushes to `main` or `migrate-to-vercel` that touch `web/` trigger automated build and deploy to the VPS.

---

## Design Decisions

**No background jobs on the frontend.** The old Streamlit Cloud app ran alert checking in-process, which died when the app hibernated. The VPS daemon (`sentinel-daemon`) is the only alert checker -- it runs 24/7 as a systemd service.

**VPS is single source of truth.** Auth, watchlists, alerts, and preferences all live in the VPS SQLite database. No split-brain between local and remote storage.

**Caching for expensive endpoints.** The enriched watchlist endpoint (`/api/watchlist/<id>/enriched`) fetches yfinance data for every ticker. An in-memory cache with 5-minute TTL keeps response times under 10ms for repeated polls. Invalidated on watchlist add/remove/clear. Without caching, a 10-ticker watchlist takes 10-20s per poll.

**Chart libraries.** TradingView Lightweight Charts for price data (~45KB, purpose-built for financial charts). Recharts via shadcn/ui for all other charts. Plotly was avoided due to its 2MB bundle size and SSR issues with Next.js App Router.

**Plain English first.** Every score and metric card answers "what does this mean for me?" No unexplained jargon.

---

## Known Gaps

- Supply chain choropleth map (was Plotly -- pending D3 or force-graph port)
- Email notifications (Telegram and browser push only for now)

---

## Disclaimer

**This tool is for educational and informational purposes only.** It does not constitute financial advice, investment recommendation, or solicitation to trade. All scores and narratives are computed automatically from publicly available data and may contain errors or omissions. Always do your own research before making investment decisions. Past performance does not guarantee future results.

---

## License

MIT -- see [LICENSE](LICENSE) for details.

---

*Built for anyone who wants to understand stocks without a finance degree.*
