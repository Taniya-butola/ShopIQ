"""
utils/price_predictor.py

Optional ML feature: Predict whether a product's price will rise or fall
in the next 7 days using a simple linear regression model trained on
historical price snapshots.

Requirements: scikit-learn, numpy (already in requirements.txt)

Usage:
    from utils.price_predictor import predict_price_trend
    trend = predict_price_trend(history_records)
    # Returns: { direction: "up"|"down"|"stable", predicted_price: float,
    #            confidence: float, reason: str }
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

import numpy as np

logger = logging.getLogger(__name__)


def predict_price_trend(history: list[dict[str, Any]]) -> dict[str, Any]:
    """
    Fit a linear regression to price history and project 7 days forward.

    Args:
        history: List of dicts with keys 'price' and 'recorded_at' (ISO string)

    Returns:
        {
          "direction": "up" | "down" | "stable",
          "current_price": float,
          "predicted_price": float,
          "change_pct": float,
          "confidence": float,   # R² of the fit, 0–1
          "reason": str,
        }
    """
    if len(history) < 3:
        return _insufficient_data(history)

    try:
        from sklearn.linear_model import LinearRegression
        from sklearn.metrics import r2_score
    except ImportError:
        logger.warning("scikit-learn not installed — price prediction unavailable.")
        return _insufficient_data(history)

    # Convert timestamps → day offsets (day 0 = first record)
    try:
        t0 = datetime.fromisoformat(history[0]["recorded_at"])
        x = np.array([
            (datetime.fromisoformat(r["recorded_at"]) - t0).days
            for r in history
        ]).reshape(-1, 1)
        y = np.array([r["price"] for r in history], dtype=float)
    except (KeyError, ValueError) as exc:
        logger.warning(f"Price prediction data error: {exc}")
        return _insufficient_data(history)

    # Fit
    model = LinearRegression()
    model.fit(x, y)
    y_pred = model.predict(x)
    r2 = float(r2_score(y, y_pred))

    # Predict 7 days ahead
    last_day = int(x[-1][0])
    predicted_price = float(model.predict([[last_day + 7]])[0])
    current_price = float(y[-1])
    change_pct = ((predicted_price - current_price) / current_price) * 100

    # Direction thresholds
    if abs(change_pct) < 1.5:
        direction = "stable"
        reason = "Price has been relatively stable. No significant movement expected."
    elif change_pct > 0:
        direction = "up"
        reason = (
            f"Price trend suggests a rise of ~{change_pct:.1f}% over the next 7 days. "
            "Consider buying sooner."
        )
    else:
        direction = "down"
        reason = (
            f"Price trend suggests a drop of ~{abs(change_pct):.1f}% over the next 7 days. "
            "It may be worth waiting."
        )

    return {
        "direction": direction,
        "current_price": round(current_price, 2),
        "predicted_price": round(max(predicted_price, 0), 2),
        "change_pct": round(change_pct, 2),
        "confidence": round(max(r2, 0), 3),
        "reason": reason,
        "data_points": len(history),
    }


def _insufficient_data(history: list[dict]) -> dict[str, Any]:
    current = history[-1]["price"] if history else None
    return {
        "direction": "unknown",
        "current_price": current,
        "predicted_price": None,
        "change_pct": None,
        "confidence": 0,
        "reason": "Not enough price history to make a prediction (need at least 3 data points).",
        "data_points": len(history),
    }
