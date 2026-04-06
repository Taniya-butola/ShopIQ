"""
utils/deal_suggester.py

Scores all products in a search result set and returns the best deal
with a human-readable explanation. Uses a weighted scoring model.

Scoring factors:
  - Price (lower is better)              weight: 0.45
  - Rating (higher is better)            weight: 0.30
  - Discount % (higher is better)        weight: 0.15
  - Review count (more reviews = trust)  weight: 0.10
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

WEIGHTS = {
    "price":        0.45,
    "rating":       0.30,
    "discount_pct": 0.15,
    "review_count": 0.10,
}


def suggest_best_deal(search_results: dict[str, Any]) -> dict[str, Any]:
    """
    Analyse `search_results["products"]` and return a suggestion dict:
    {
      "product": Product,
      "score": float,
      "reasoning": str,
      "savings": float | None,
    }
    """
    products = search_results.get("products", [])
    if not products:
        return {"error": "No products to analyse."}

    scored = []
    for p in products:
        score = _compute_score(p, products)
        scored.append((score, p))

    scored.sort(key=lambda x: x[0], reverse=True)
    best_score, best = scored[0]

    # Build explanation
    cheapest_price = min(p.get("price", float("inf")) for p in products)
    avg_price = sum(p.get("price", 0) for p in products) / len(products)

    reasons = []
    if best.get("price") and best["price"] == cheapest_price:
        reasons.append("lowest price across all platforms")
    if best.get("rating", 0) and best["rating"] >= 4.3:
        reasons.append(f"highly rated ({best['rating']}/5)")
    if best.get("discount_pct") and best["discount_pct"] >= 20:
        reasons.append(f"{best['discount_pct']}% discount applied")
    if best.get("review_count") and best["review_count"] > 1000:
        reasons.append(f"backed by {best['review_count']:,} reviews")

    reasoning = (
        "This is the best deal because it offers "
        + (", ".join(reasons) if reasons else "the best overall value score")
        + "."
    )

    savings = (avg_price - best["price"]) if best.get("price") else None

    return {
        "product": best,
        "score": round(best_score, 4),
        "reasoning": reasoning,
        "savings_vs_average": round(savings, 2) if savings else None,
    }


def _compute_score(product: dict, all_products: list[dict]) -> float:
    """Normalise each factor to [0, 1] and compute weighted sum."""
    prices  = [p.get("price", 0) for p in all_products if p.get("price")]
    ratings = [p.get("rating", 0) for p in all_products if p.get("rating")]
    discounts = [p.get("discount_pct", 0) for p in all_products if p.get("discount_pct")]
    reviews = [p.get("review_count", 0) for p in all_products if p.get("review_count")]

    score = 0.0

    # Price: invert (cheaper = higher score)
    if prices:
        min_p, max_p = min(prices), max(prices)
        if max_p > min_p:
            price_norm = 1 - (product.get("price", max_p) - min_p) / (max_p - min_p)
        else:
            price_norm = 1.0
        score += WEIGHTS["price"] * price_norm

    # Rating
    if ratings:
        min_r, max_r = min(ratings), max(ratings)
        if max_r > min_r:
            rating_norm = (product.get("rating", min_r) - min_r) / (max_r - min_r)
        else:
            rating_norm = 1.0
        score += WEIGHTS["rating"] * rating_norm

    # Discount %
    if discounts:
        max_d = max(discounts)
        if max_d > 0:
            disc_norm = product.get("discount_pct", 0) / max_d
        else:
            disc_norm = 0.0
        score += WEIGHTS["discount_pct"] * disc_norm

    # Review count (log-normalised)
    import math
    if reviews:
        max_rev = max(reviews)
        rev = product.get("review_count", 0)
        if max_rev > 0 and rev > 0:
            rev_norm = math.log1p(rev) / math.log1p(max_rev)
        else:
            rev_norm = 0.0
        score += WEIGHTS["review_count"] * rev_norm

    return score
