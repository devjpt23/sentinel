"""
Strategy Simulation Engine.
Backtests buy/sell rules against historical price data.
Core engine used by the Monte Carlo runner.
"""

import pandas as pd
import numpy as np
from typing import Optional, Dict, Any


def compute_indicators(price_series: pd.Series, volume_series: Optional[pd.Series] = None) -> pd.DataFrame:
    """Compute technical indicators from daily price history.

    Args:
        price_series: Daily closing prices (DateTimeIndex)
        volume_series: Daily volume (DateTimeIndex)

    Returns:
        DataFrame with columns: close, sma_50, sma_200, rsi_14,
                                pct_off_52w_high, drawdown_pct, volatility_20,
                                avg_volume_20, volume_ratio
    """
    df = pd.DataFrame({"close": price_series})

    # Moving averages
    df["sma_50"] = df["close"].rolling(50).mean()
    df["sma_200"] = df["close"].rolling(200).mean()

    # RSI-14 using Wilder's smoothing
    delta = df["close"].diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(alpha=1/14, min_periods=14).mean()
    avg_loss = loss.ewm(alpha=1/14, min_periods=14).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    df["rsi_14"] = 100 - (100 / (1 + rs))

    # % from 52-week high
    roll_max_52w = df["close"].rolling(252).max()
    df["pct_off_52w_high"] = (df["close"] - roll_max_52w) / roll_max_52w * 100

    # Drawdown from peak
    peak = df["close"].cummax()
    df["drawdown_pct"] = (df["close"] - peak) / peak * 100

    # 20-day volatility (annualized)
    df["volatility_20"] = df["close"].pct_change().rolling(20).std() * np.sqrt(252)

    # Volume metrics
    if volume_series is not None and not volume_series.empty:
        df["volume"] = volume_series
        df["avg_volume_20"] = df["volume"].rolling(20).mean()
        df["volume_ratio"] = df["volume"] / df["avg_volume_20"]
    else:
        df["avg_volume_20"] = np.nan
        df["volume_ratio"] = np.nan

    return df


def run_trade(
    price_df: pd.DataFrame,
    entry_idx: int,
    params: Dict[str, Any],
) -> Dict[str, Any]:
    """Run a single simulated trade from entry_idx onward.

    Args:
        price_df: DataFrame with columns [close, sma_50, sma_200, rsi_14, ...]
        entry_idx: Row index in price_df to enter
        params: Simulation parameters

    Returns:
        dict with: entry_date, entry_price, exit_date, exit_price,
                   return_pct, max_drawdown, hold_days, exit_reason
    """
    entry_price = price_df.iloc[entry_idx]["close"]
    entry_date = price_df.index[entry_idx]

    take_profit_pct = params.get("take_profit_pct", 0.20)
    stop_loss_pct = params.get("stop_loss_pct", 0.15)
    max_hold_days = params.get("max_hold_days", 365)

    exit_idx = None
    exit_reason = "max_hold"

    # Walk forward from entry date
    for i in range(entry_idx + 1, min(entry_idx + max_hold_days + 1, len(price_df))):
        current_price = price_df.iloc[i]["close"]
        return_pct = (current_price - entry_price) / entry_price

        # Check stop loss first (safety)
        if return_pct <= -stop_loss_pct:
            exit_idx = i
            exit_reason = "stop_loss"
            break

        # Check take profit
        if return_pct >= take_profit_pct:
            exit_idx = i
            exit_reason = "take_profit"
            break

    # If no exit triggered, exit at max hold or end of data
    if exit_idx is None:
        exit_idx = min(entry_idx + max_hold_days, len(price_df) - 1)
        if exit_idx == entry_idx:
            return {"error": "no_data_after_entry"}

    exit_price = price_df.iloc[exit_idx]["close"]
    exit_date = price_df.index[exit_idx]
    return_pct = (exit_price - entry_price) / entry_price
    hold_days = (exit_date - entry_date).days

    # Compute max drawdown during hold
    prices_held = price_df.iloc[entry_idx:exit_idx + 1]["close"]
    peak = prices_held.cummax()
    drawdowns = (prices_held - peak) / peak
    max_drawdown = drawdowns.min() if not drawdowns.empty else 0.0

    # Sharpe ratio (simplified: annualized return / annualized volatility)
    daily_returns = prices_held.pct_change().dropna()
    if len(daily_returns) > 1 and daily_returns.std() > 0:
        annualized_return = (1 + return_pct) ** (252 / hold_days) - 1 if hold_days > 0 else 0
        sharpe = annualized_return / (daily_returns.std() * np.sqrt(252))
    else:
        sharpe = 0.0

    return {
        "entry_date": entry_date,
        "entry_price": round(entry_price, 2),
        "exit_date": exit_date,
        "exit_price": round(exit_price, 2),
        "return_pct": round(return_pct * 100, 2),
        "max_drawdown_pct": round(max_drawdown * 100, 1),
        "hold_days": hold_days,
        "exit_reason": exit_reason,
        "sharpe": round(sharpe, 2),
    }


def run_batch(
    price_df: pd.DataFrame,
    params: Dict[str, Any],
    n_runs: int = 1000,
    seed: Optional[int] = None,
) -> Dict[str, Any]:
    """Run batch simulation with random entry points.

    Args:
        price_df: Price data with computed indicators
        params: Simulation parameters
        n_runs: Number of random entry attempts
        seed: Random seed for reproducibility

    Returns:
        dict with trade history, aggregate stats, parameter summary
    """
    if seed is not None:
        np.random.seed(seed)

    # Compute indicators if not already present
    if "rsi_14" not in price_df.columns:
        # yfinance returns "Close", not "close"
        close_col = "Close" if "Close" in price_df.columns else "close"
        volume_col = "Volume" if "Volume" in price_df.columns else None
        vol = price_df[volume_col] if volume_col else None
        price_df = compute_indicators(price_df[close_col], vol)
    else:
        # Ensure we have the required columns
        price_df = price_df.copy()

    # Entry rules — "RSI must be below X" for oversold entry
    max_rsi = params.get("max_rsi", 40)
    min_pullback = params.get("min_pullback", 5.0)  # must be down X% from 52w high
    above_200ma = params.get("above_200ma", False)  # must be above 200-day MA?
    min_volume_ratio = params.get("min_volume_ratio", 0)  # 0 = no volume filter

    # Valid entry range (skip first 200 days for indicator warmup, skip last 30 to allow room for exit)
    warmup = 210
    end_buffer = 30
    max_idx = len(price_df) - end_buffer

    trades = []
    attempts = 0

    while len(trades) < n_runs and attempts < n_runs * 20:
        attempts += 1
        idx = np.random.randint(warmup, max_idx)
        row = price_df.iloc[idx]

        # Check timing rules
        rsi = row.get("rsi_14")
        if rsi is not None and not pd.isna(rsi) and rsi > max_rsi:
            continue  # not oversold enough
        if rsi is not None and pd.isna(rsi):
            continue

        pullback = row.get("pct_off_52w_high")
        if pullback is not None and not pd.isna(pullback):
            if pullback > -min_pullback:
                continue  # not pulled back enough
        else:
            continue

        # Check MA filter
        close = row.get("close")
        sma_200 = row.get("sma_200")
        if above_200ma:
            if sma_200 is None or pd.isna(sma_200) or close < sma_200:
                continue

        # Check volume confirmation — volume > N × 20-day average
        if min_volume_ratio > 0:
            vol_ratio = row.get("volume_ratio")
            if vol_ratio is None or pd.isna(vol_ratio) or vol_ratio < min_volume_ratio:
                continue  # volume too low to confirm the entry

        # Fundamental quality filter — only enter if scores meet thresholds
        min_health = params.get("min_health_score", 0)
        min_intrinsic = params.get("min_intrinsic_score", 0)
        if min_health > 0 or min_intrinsic > 0:
            health_score = params.get("_health_score", 50)
            intrinsic_score = params.get("_intrinsic_score", 50)
            if health_score < min_health or intrinsic_score < min_intrinsic:
                continue

        # All checks passed — run the trade
        trade = run_trade(price_df, idx, params)
        if "error" not in trade:
            trades.append(trade)

        if attempts >= n_runs * 20:
            break

    # Compute aggregates
    if not trades:
        return {
            "trades": [],
            "total_runs": 0,
            "params": params,
            "error": "No trades generated — try looser entry rules.",
        }

    returns = [t["return_pct"] for t in trades]
    dd = [t["max_drawdown_pct"] for t in trades]
    holds = [t["hold_days"] for t in trades]
    wins = [r for r in returns if r > 0]

    return_pctiles = np.percentile(returns, [10, 25, 50, 75, 90])

    stats = {
        "total_runs": len(trades),
        "win_rate": round(len(wins) / len(trades) * 100, 1) if trades else 0,
        "median_return": round(float(np.median(returns)), 1),
        "mean_return": round(float(np.mean(returns)), 1),
        "best_return": round(float(np.max(returns)), 1),
        "worst_return": round(float(np.min(returns)), 1),
        "median_drawdown": round(float(np.median(dd)), 1),
        "worst_drawdown": round(float(np.min(dd)), 1),
        "median_hold_days": int(np.median(holds)),
        "pctile_10": round(float(return_pctiles[0]), 1),
        "pctile_25": round(float(return_pctiles[1]), 1),
        "pctile_50": round(float(return_pctiles[2]), 1),
        "pctile_75": round(float(return_pctiles[3]), 1),
        "pctile_90": round(float(return_pctiles[4]), 1),
        "avg_sharpe": round(float(np.mean([t.get("sharpe", 0) for t in trades])), 2),
    }

    return {
        "trades": trades,
        "stats": stats,
        "total_runs": len(trades),
        "params": params,
    }
