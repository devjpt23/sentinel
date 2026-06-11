"""
Persistent watchlist storage using SQLite.

Stores watchlist tickers in a local SQLite database so the watchlist
survives browser tab closes, session expirations, and server restarts.
This is essential for deployed websites where Streamlit sessions are ephemeral.

Usage:
    from src.data.watchlist_db import init_db, load_watchlist, add_ticker, remove_ticker, clear_watchlist

    init_db()                          # run once at startup
    tickers = load_watchlist()         # get all saved tickers
    add_ticker("AAPL")                 # add one
    remove_ticker("AAPL")              # remove one
    clear_watchlist()                  # remove all
"""

import sqlite3
import os
from typing import List

# Store the DB file alongside the app in the project root
_DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "watchlist.db")


def _get_conn() -> sqlite3.Connection:
    """Get a connection to the watchlist database."""
    conn = sqlite3.connect(_DB_PATH)
    conn.execute("PRAGMA journal_mode=WAL")  # better concurrency for web use
    return conn


def init_db() -> None:
    """Create the watchlist table if it doesn't exist. Safe to call on every startup."""
    conn = _get_conn()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS watchlist (
            ticker TEXT PRIMARY KEY,
            added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    conn.close()


def load_watchlist() -> List[str]:
    """Return all tickers in the watchlist, ordered by most recently added."""
    conn = _get_conn()
    rows = conn.execute("SELECT ticker FROM watchlist ORDER BY added_at DESC").fetchall()
    conn.close()
    return [row[0] for row in rows]


def add_ticker(ticker: str) -> None:
    """Add a ticker to the watchlist. Ignores duplicates."""
    conn = _get_conn()
    conn.execute("INSERT OR IGNORE INTO watchlist (ticker) VALUES (?)", (ticker.upper(),))
    conn.commit()
    conn.close()


def remove_ticker(ticker: str) -> None:
    """Remove a ticker from the watchlist."""
    conn = _get_conn()
    conn.execute("DELETE FROM watchlist WHERE ticker = ?", (ticker.upper(),))
    conn.commit()
    conn.close()


def clear_watchlist() -> None:
    """Remove all tickers from the watchlist."""
    conn = _get_conn()
    conn.execute("DELETE FROM watchlist")
    conn.commit()
    conn.close()
