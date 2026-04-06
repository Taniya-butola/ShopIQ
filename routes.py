"""
api/routes.py — REST API endpoints for the price comparison engine.

Endpoints:
  GET  /api/search?q=<query>&platforms=<csv>&min_price=<n>&max_price=<n>&sort=<field>
  GET  /api/product/<id>/history
  POST /api/alerts
  GET  /api/alerts
  DELETE /api/alerts/<id>
  GET  /api/suggest?q=<query>        (autocomplete)
  GET  /api/best-deal/<query>        (AI best-deal suggestion)
"""

import logging
from flask import Blueprint, request, jsonify, current_app

from search_coordinator import SearchCoordinator
from cache import CacheManager
from price_history import PriceHistoryModel
from alerts import AlertModel
from deal_suggester import suggest_best_deal

logger = logging.getLogger(__name__)
api_bp = Blueprint("api", __name__)


# ─── Helper ───────────────────────────────────────────────────────────────────
def _error(msg: str, code: int = 400):
    return jsonify({"success": False, "error": msg}), code


# ─── Search ───────────────────────────────────────────────────────────────────
@api_bp.route("/search", methods=["GET"])
def search():
    """
    Search products across multiple platforms.

    Query params:
      q           — search query (required)
      platforms   — comma-separated list: amazon,flipkart,snapdeal,croma (default: all)
      sort        — price_asc | price_desc | rating_desc (default: price_asc)
      min_price   — minimum price filter
      max_price   — maximum price filter
      min_rating  — minimum rating filter (0-5)
    """
    query = request.args.get("q", "").strip()
    if not query:
        return _error("Query parameter 'q' is required.")

    # Parse optional filters
    platforms_raw = request.args.get("platforms", "")
    platforms = [p.strip() for p in platforms_raw.split(",") if p.strip()] or None

    sort_by = request.args.get("sort", "price_asc")
    try:
        min_price = float(request.args.get("min_price", 0))
        max_price = float(request.args.get("max_price", float("inf")))
        min_rating = float(request.args.get("min_rating", 0))
    except ValueError:
        return _error("min_price, max_price, and min_rating must be numeric.")

    # Check cache first
    cache = CacheManager()
    cache_key = f"search:{query}:{platforms}:{sort_by}:{min_price}:{max_price}:{min_rating}"
    cached = cache.get(cache_key)
    if cached:
        logger.info(f"Cache HIT for query='{query}'")
        return jsonify({"success": True, "data": cached, "source": "cache"})

    # Run scrapers in parallel
    coordinator = SearchCoordinator(max_workers=current_app.config["MAX_SCRAPERS"])
    try:
        results = coordinator.search(
            query=query,
            platforms=platforms,
            min_price=min_price,
            max_price=max_price,
            min_rating=min_rating,
            sort_by=sort_by,
        )
    except Exception as exc:
        logger.exception(f"Search failed for query='{query}': {exc}")
        return _error(f"Search failed: {str(exc)}", 500)

    # Store price snapshots for history tracking
    PriceHistoryModel.record_snapshot(query, results)

    # Cache the result
    cache.set(cache_key, results, ttl=current_app.config["CACHE_TTL"])

    return jsonify({"success": True, "data": results, "source": "live"})


# ─── Price History ────────────────────────────────────────────────────────────
@api_bp.route("/product/<product_id>/history", methods=["GET"])
def price_history(product_id: str):
    """Return price history for a specific product (last 90 days)."""
    days = int(request.args.get("days", 90))
    history = PriceHistoryModel.get_history(product_id, days=days)
    if history is None:
        return _error("Product not found.", 404)
    return jsonify({"success": True, "data": history})


# ─── Price Drop Alerts ────────────────────────────────────────────────────────
@api_bp.route("/alerts", methods=["POST"])
def create_alert():
    """
    Create a price-drop alert.
    Body JSON: { email, product_id, product_name, target_price, platform }
    """
    body = request.get_json(silent=True)
    if not body:
        return _error("Request body must be JSON.")

    required = ["email", "product_id", "product_name", "target_price"]
    missing = [f for f in required if f not in body]
    if missing:
        return _error(f"Missing fields: {', '.join(missing)}")

    alert = AlertModel.create(
        email=body["email"],
        product_id=body["product_id"],
        product_name=body["product_name"],
        target_price=float(body["target_price"]),
        platform=body.get("platform"),
    )
    return jsonify({"success": True, "data": alert}), 201


@api_bp.route("/alerts", methods=["GET"])
def list_alerts():
    """List all alerts for an email address."""
    email = request.args.get("email", "").strip()
    if not email:
        return _error("Query parameter 'email' is required.")
    alerts = AlertModel.list_for_email(email)
    return jsonify({"success": True, "data": alerts})


@api_bp.route("/alerts/<alert_id>", methods=["DELETE"])
def delete_alert(alert_id: str):
    """Delete a price-drop alert."""
    deleted = AlertModel.delete(alert_id)
    if not deleted:
        return _error("Alert not found.", 404)
    return jsonify({"success": True, "message": "Alert deleted."})


# ─── Autocomplete / Suggestions ───────────────────────────────────────────────
@api_bp.route("/suggest", methods=["GET"])
def suggest():
    """Return autocomplete suggestions from past searches."""
    q = request.args.get("q", "").strip()
    if len(q) < 2:
        return jsonify({"success": True, "data": []})
    suggestions = PriceHistoryModel.get_popular_searches(prefix=q, limit=8)
    return jsonify({"success": True, "data": suggestions})


# ─── Best Deal AI Suggestion ──────────────────────────────────────────────────
@api_bp.route("/best-deal", methods=["GET"])
def best_deal():
    """
    Analyse current results and suggest the best deal.
    Considers: price, rating, platform reputation, delivery speed.
    """
    query = request.args.get("q", "").strip()
    if not query:
        return _error("Query parameter 'q' is required.")

    cache = CacheManager()
    cached_results = cache.get(f"search:{query}:None:price_asc:0:inf:0")
    if not cached_results:
        return _error("Run a search first to enable best-deal suggestions.", 400)

    try:
        suggestion = suggest_best_deal(cached_results)
    except Exception as exc:
        logger.exception(f"Best-deal suggestion failed: {exc}")
        return _error("Could not compute best deal.", 500)

    return jsonify({"success": True, "data": suggestion})
