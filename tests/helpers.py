"""Test helper functions for notification test suites."""

import json
from typing import Dict, Optional


def seed_user_watchlist(conn, user_id: int, tickers):
    """Insert tickers into user_watchlist for a test user."""
    for t in tickers:
        conn.execute(
            "INSERT OR IGNORE INTO user_watchlist (user_id, ticker) VALUES (?, ?)",
            (user_id, t),
        )
    conn.commit()


def seed_custom_alert_rule(
    conn,
    user_id: int = 1,
    ticker: str = "NVDA",
    signal_id: str = "price",
    operator: str = ">",
    value: float = 150.0,
    enabled: bool = True,
    scope: str = "single",
    logic_operator: str = "AND",
    severity: str = "info",
    currently_triggered: int = 0,
    name: Optional[str] = None,
) -> int:
    """Insert a custom alert rule and return its ID."""
    conditions = json.dumps([
        {"signal_id": signal_id, "operator": operator, "value": value}
    ])
    conn.execute(
        """INSERT INTO custom_alert_rules
           (user_id, ticker, name, conditions, logic_operator, severity,
            scope, enabled, currently_triggered)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            user_id,
            ticker if scope == "single" else None,
            name or f"Test {signal_id} {operator} {value}",
            conditions,
            logic_operator,
            severity,
            scope,
            1 if enabled else 0,
            currently_triggered,
        ),
    )
    conn.commit()
    return conn.execute("SELECT last_insert_rowid()").fetchone()[0]


def make_market_data(price: float = 150.0) -> Dict:
    """Build a minimal market data dict for reconciliation tests."""
    return {
        "market": {
            "price": price,
            "avg_volume": 50000000,
            "52w_high": 200.0,
            "52w_low": 100.0,
        },
        "valuation": {"pe_ttm": 25.0, "pb_ratio": 5.0},
        "health": {"debt_to_equity": 50.0},
        "per_share": {"dividend_yield": 0.5},
    }
