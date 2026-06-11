"""
Scoring utilities for color coding and verdict mapping.
Shared across all scoring modules.
"""

from typing import Optional, Tuple


def score_to_color(score: int, low: int = 40, high: int = 70) -> str:
    """Map a 0-100 score to traffic light color."""
    if score >= high:
        return "#00C853"  # green
    elif score >= low:
        return "#FFD600"  # yellow
    return "#FF1744"  # red


def score_to_verdict(score: int, low: int = 40, high: int = 70) -> str:
    """Map a 0-100 score to a plain-English verdict."""
    if score >= high:
        return "Strong"
    elif score >= low:
        return "Moderate"
    return "Weak"


def score_to_emoji(score: int, low: int = 40, high: int = 70) -> str:
    """Map a 0-100 score to a traffic light emoji."""
    if score >= high:
        return "🟢"
    elif score >= low:
        return "🟡"
    return "🔴"


def normalize_score(value: float, best: float, worst: float, invert: bool = False) -> float:
    """Normalize a metric to 0-100 scale given best/worst bounds.

    If invert=True, lower values are better (e.g., P/E, debt).
    """
    if best == worst:
        return 50.0

    if invert:
        value, best, worst = -value, -best, -worst

    normalized = ((value - worst) / (best - worst)) * 100
    return max(0, min(100, normalized))


def safe_div(a: Optional[float], b: Optional[float]) -> Optional[float]:
    """Safely divide two numbers, returning None if either is None or zero."""
    if a is None or b is None or b == 0:
        return None
    return a / b
