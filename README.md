# 📊 Sentinel 

**Fundamental Analysis Made Simple.**

Sentinel is a Streamlit dashboard that gives you instant, plain-English answers about any stock. Type a ticker, and Sentinel analyzes the company's financial health, price fairness, intrinsic worth, and risk — then explains what it all means in language anyone can understand.

![Python](https://img.shields.io/badge/python-%3E%3D3.10-blue)
![Streamlit](https://img.shields.io/badge/streamlit-%3E%3D1.28.0-red)
![License](https://img.shields.io/badge/license-MIT-green)

---

## Why Sentinel?

Most stock analysis tools overwhelm you with 50+ metrics, jargon like "EV/EBITDA multiple expansion," and assume you have a finance degree. **We think that's wrong.**

Sentinel answers the only three questions that matter for any stock:

1. **Is this a good company?** — Health Score
2. **Is the price fair?** — Price vs. Peers & Intrinsic Worth
3. **What could go wrong?** — Risk Assessment & Red Flags

Every number comes with a plain-English explanation. No finance degree required.

---

## What You Get

| Section | What It Shows |
|---------|---------------|
| **Headline Cards** | Four color-coded scores: Health, Price vs Peers, Intrinsic Worth, Risk |
| **The Story** | A one-paragraph narrative that explains the stock in plain English |
| **Key Numbers** | 12+ core metrics (P/E, ROE, Margins, Growth, Debt, Beta, FCF) — each with a "what this means" tooltip |
| **Analyst Consensus** | Aggregate ratings, target price, and number of analysts covering |
| **Peer Comparison** | Side-by-side table vs. similar companies in the same industry |
| **Red Flags & Risks** | Automated warnings for debt, cash flow, growth, and valuation concerns |
| **Institutional Activity** | Top holders, recent buying/selling by major institutions |
| **News Sentiment** | Recent headlines with bullish/bearish/neutral classification |
| **Market Context** | VIX, S&P 500 trend, yield curve, major indices strip |
| **Trend Charts** | 5-year sparklines for revenue, profit, debt, and stock price |
| **Deep Dive** | Full financial statements, F-Score breakdown, Z-Score analysis, DCF model |
| **Live Price Ticker** | Real-time (delayed) price with daily change |
| **Watchlist** | Save stocks and monitor their health at a glance with a scrolling marquee |
| **Strategy Lab** | Monte Carlo simulation — backtest buy/sell rules against 5 years of price data |
| **Sector Search** | Browse and discover stocks within major sectors |
| **PDF Export** | Download a formatted PDF report of any analysis |

---

## How It Works

Sentinel pulls financial data from **Yahoo Finance** (via `yfinance`) and runs it through proven, battle-tested scoring systems:

- **Piotroski F-Score** — A 9-point checklist of financial strength covering profitability, leverage, and operating efficiency. Developed by accounting professor Joseph Piotroski.
- **Altman Z-Score** — Bankruptcy risk prediction formula used by credit analysts since 1968. Combines profitability, leverage, liquidity, and market value.
- **Peer Comparison** — Your stock vs. industry averages. Are you paying more or less than similar companies? Is growth better or worse?
- **Red Flag Detection** — Automated checks for negative earnings, debt exceeding cash, declining revenue, extreme valuations, and negative free cash flow.
- **DCF & Graham Number** — Conservative absolute valuation estimates based on cash flows and book value.

Then Sentinel translates everything into **plain English** — every metric card and score card answers "what does this mean for me?"

---

## Architecture

```
sentinel/
├── app.py                          # Main Streamlit dashboard
├── src/
│   ├── data/
│   │   ├── fetcher.py              # yfinance data fetching & enrichment
│   │   ├── company_links.py        # Company relationship graph
│   │   └── sector_universe.py      # Sector/industry classifications
│   ├── scoring/
│   │   ├── health.py               # F-Score + composite Health Score (0–100)
│   │   ├── zscore.py               # Altman Z-Score
│   │   ├── valuation.py            # Price vs. Peers verdict
│   │   ├── intrinsic.py            # Intrinsic worth (Graham, DCF, FCF yield)
│   │   ├── risk.py                 # Risk assessment & red flag detection
│   │   └── common.py               # Shared scoring utilities (color, emoji, normalize)
│   ├── display/
│   │   ├── deep_dive.py            # Financial statements, DCF model, score breakdowns
│   │   ├── live_price.py           # Auto-refreshing live price ticker
│   │   ├── macro_strip.py          # VIX, S&P trend, yield curve display
│   │   ├── sentiment.py            # News sentiment analysis & institutional activity
│   │   ├── sector_search.py        # Sector-based stock discovery
│   │   ├── strategy_sim.py         # Strategy Lab UI (Monte Carlo simulator)
│   │   ├── company_linkage.py      # Supply chain & competitor relationship graph
│   │   └── pdf_report.py           # PDF report generation
│   ├── strategy/
│   │   └── engine.py               # Backtesting engine with technical indicators
│   └── utils/
│       ├── explanations.py         # Plain-English metric explanations
│       └── formatters.py           # Number formatting utilities
└── pyproject.toml
```

**Data flow:** `data/` → `scoring/` → `display/`, with scoring modules that are multi-signal and resistant to single-metric distortion.

---

## Getting Started

### Prerequisites

- **Python** ≥ 3.10
- **uv** (recommended) or pip

### Installation

```bash
# Clone the repository
git clone https://github.com/your-org/sentinel.git
cd sentinel

# Install dependencies with uv
uv sync

# Or with pip
pip install -e .
```

### Running the Dashboard

```bash
# Using the installed entry point
sentinel

# Or directly
streamlit run app.py
```

Then open **http://localhost:8501** in your browser. Type a stock ticker (e.g., `NVDA`, `AAPL`) in the search bar and press Enter.

### Example Tickers

`NVDA` • `AAPL` • `TSLA` • `MSFT` • `GOOGL` • `AMZN` • `META` • `JPM` • `XOM` • `JNJ`

---

## Features in Detail

### 🏠 Dashboard
The main analysis view. Enter a ticker to get the full fundamental breakdown: four headline scores, a narrative story, key numbers with explanations, analyst consensus, peer comparison, red flags, news sentiment, market context, and 5-year trends. An empty state shows top daily movers, market news, and major indices while you decide what to analyze.

### 📋 Watchlist
Save stocks you're tracking and see their health scores at a glance. Each card shows current price, P/E ratio, and health verdict with a color-coded indicator. A scrolling marquee at the top of every page shows live prices for your watchlist, updating on hover.

### 🎯 Strategy Lab
A Monte Carlo simulator that backtests custom buy/sell rules against 5 years of historical price data. Configure entry conditions (RSI, SMA pullback, volume confirmation, fundamental quality filters), exit rules (profit target, stop loss, time horizon), and position sizing. Run 10,000 randomized simulations to see your win rate, average return, and return distribution.

### 🔍 Sector Search
Browse stocks by sector with filtering by market cap and health. Discover new investment ideas without needing to know ticker symbols in advance.

### ℹ️ About
Explains the methodology behind each score, the data sources, and important disclaimers.

---

## Design Philosophy

- **Plain English first.** Every number answers "what does this mean?" — no jargon, no assumptions.
- **Dark by default.** Professional financial terminal aesthetic with a dark theme and card-based layout. Light mode available as a toggle.
- **Multi-signal scoring.** No single metric determines a verdict. Scores combine multiple inputs for resilience against outliers and data gaps.
- **Read-only research tool.** Sentinel is a fundamental research assistant — not a trading system, screener, portfolio manager, or real-time alerting engine.
- **Zero API keys required.** All data comes from the free Yahoo Finance API. No sign-up, no billing, no limits.

---

## Dependencies

| Package | Purpose |
|---------|---------|
| [Streamlit](https://streamlit.io/) | Web application framework |
| [yfinance](https://github.com/ranaroussi/yfinance) | Financial data from Yahoo Finance |
| [Plotly](https://plotly.com/python/) | Interactive charts and sparklines |
| [Pandas](https://pandas.pydata.org/) | Data manipulation and analysis |
| [NumPy](https://numpy.org/) | Numerical computation |
| [fpdf2](https://pyfpdf.github.io/fpdf2/) | PDF report generation |
| [lxml](https://lxml.de/) | XML/HTML parsing for web scraping |

---

## Disclaimer

**This tool is for educational and informational purposes only.** It does not constitute financial advice, investment recommendation, or solicitation to trade. All scores and narratives are computed automatically from publicly available data and may contain errors or omissions. Always do your own research before making investment decisions. Past performance does not guarantee future results. The authors assume no liability for any financial losses incurred based on information presented by this tool.

---

## License

MIT — see [LICENSE](LICENSE) for details.

---

*Built for everyone who wants to understand stocks without a finance degree.*
