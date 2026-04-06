"""
utils/search_coordinator.py

Orchestrates parallel scraping across all registered platforms,
deduplicates results, applies filters, and sorts output.
"""

from __future__ import annotations

import logging
import os
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any

from amazon_scraper import AmazonScraper
from flipkart_scraper import FlipkartScraper

from demo_scraper import DemoScraper          # Safe mock data for dev/demo
from serpapi_scraper import SerpApiScraper

logger = logging.getLogger(__name__)

# Registry of all supported scrapers: key → scraper class
def _is_live_scraping_enabled() -> bool:
    return os.getenv("ENABLE_LIVE_SCRAPERS", "").strip().lower() in {"1", "true", "yes", "on"}


def _is_serpapi_enabled() -> bool:
    return bool(os.getenv("SERPAPI_API_KEY", "").strip())


SCRAPER_REGISTRY: dict[str, Any] = {
    "demo": DemoScraper,
}

if _is_serpapi_enabled():
    SCRAPER_REGISTRY["shopping"] = SerpApiScraper

if _is_live_scraping_enabled():
    SCRAPER_REGISTRY.update({
        "amazon": AmazonScraper,
        "flipkart": FlipkartScraper,
    })

SORT_KEYS = {
    "price_asc":    (lambda p: p.get("price", 0), False),
    "price_desc":   (lambda p: p.get("price", 0), True),
    "rating_desc":  (lambda p: p.get("rating", 0), True),
    "relevance":    (lambda p: p.get("relevance_score", 0), True),
}


class SearchCoordinator:
    """
    Runs scrapers in parallel, merges results, deduplicates,
    applies user filters, and returns a sorted product list.
    """

    def __init__(self, max_workers: int = 5):
        self.max_workers = max_workers

    # ── Public API ────────────────────────────────────────────────────────────

    def search(
        self,
        query: str,
        platforms: list[str] | None = None,
        min_price: float = 0,
        max_price: float = float("inf"),
        min_rating: float = 0,
        sort_by: str = "price_asc",
    ) -> dict[str, Any]:
        """
        Run scrape jobs in parallel and return a structured response.

        Returns:
          {
            "query": str,
            "total": int,
            "platforms_queried": [str],
            "platforms_ok": [str],
            "platforms_failed": [str],
            "products": [Product],
            "best_deal": Product | None,
          }
        """
        active_platforms = self._resolve_platforms(platforms)
        logger.info(f"Searching '{query}' on: {active_platforms}")

        # Kick off parallel scrape jobs
        raw_results: list[dict] = []
        ok: list[str] = []
        failed: list[str] = []

        with ThreadPoolExecutor(max_workers=self.max_workers) as pool:
            futures = {
                pool.submit(self._run_scraper, key, query): key
                for key in active_platforms
            }
            for future in as_completed(futures):
                key = futures[future]
                try:
                    products = future.result(timeout=20)
                    for p in products:
                        p["platform"] = p.get("platform") or key
                    raw_results.extend(products)
                    ok.append(key)
                    logger.info(f"  [{key}] returned {len(products)} products.")
                except Exception as exc:
                    logger.warning(f"  [{key}] FAILED: {exc}")
                    failed.append(key)

        # Post-process
        raw_results = self._prefer_real_results(raw_results)
        products = self._deduplicate(raw_results)
        products = self._apply_filters(products, min_price, max_price, min_rating)
        products = self._sort(products, sort_by)

        # Tag best deal
        best_deal = self._flag_best_deal(products)

        return {
            "query": query,
            "total": len(products),
            "platforms_queried": active_platforms,
            "platforms_ok": ok,
            "platforms_failed": failed,
            "products": products,
            "best_deal_id": best_deal.get("id") if best_deal else None,
        }

    # ── Private helpers ───────────────────────────────────────────────────────

    def _resolve_platforms(self, platforms: list[str] | None) -> list[str]:
        """Return validated platform keys; fall back to all registered scrapers."""
        if not platforms:
            return list(SCRAPER_REGISTRY.keys())
        valid = [p for p in platforms if p in SCRAPER_REGISTRY]
        unknown = [p for p in platforms if p not in SCRAPER_REGISTRY]
        if unknown:
            logger.warning(f"Unknown platforms ignored: {unknown}")
        return valid or list(SCRAPER_REGISTRY.keys())

    def _run_scraper(self, key: str, query: str) -> list[dict]:
        """Instantiate the scraper for `key` and run it."""
        scraper_cls = SCRAPER_REGISTRY[key]
        scraper = scraper_cls()
        return scraper.search(query)

    def _deduplicate(self, products: list[dict]) -> list[dict]:
        """
        Remove near-duplicate products across platforms.
        Two products are considered duplicates if their normalised titles
        share >80 % of tokens AND their prices are within 5 % of each other.
        The cheaper listing is kept.
        """
        seen: list[dict] = []
        for product in products:
            if not self._is_duplicate(product, seen):
                seen.append(product)
        return seen

    @staticmethod
    def _prefer_real_results(products: list[dict]) -> list[dict]:
        has_real_results = any((p.get("platform") or "") != "demo" for p in products)
        if not has_real_results:
            return products
        return [p for p in products if (p.get("platform") or "") != "demo"]

    @staticmethod
    def _normalise(title: str) -> set[str]:
        """Tokenise a title into lowercase alpha-numeric tokens."""
        return set(re.sub(r"[^a-z0-9 ]", "", title.lower()).split())

    def _is_duplicate(self, product: dict, seen: list[dict]) -> bool:
        tokens = self._normalise(product.get("title", ""))
        price = product.get("price", 0) or 0
        for s in seen:
            s_tokens = self._normalise(s.get("title", ""))
            if not tokens or not s_tokens:
                continue
            overlap = len(tokens & s_tokens) / max(len(tokens | s_tokens), 1)
            s_price = s.get("price", 0) or 0
            price_similar = (
                s_price > 0 and abs(price - s_price) / s_price < 0.05
            ) if s_price else False
            if overlap > 0.80 and price_similar:
                # Keep the cheaper one
                if price < s_price:
                    seen.remove(s)
                    return False        # Will be added by caller
                return True            # Current is more expensive → discard
        return False

    @staticmethod
    def _apply_filters(
        products: list[dict],
        min_price: float,
        max_price: float,
        min_rating: float,
    ) -> list[dict]:
        out = []
        for p in products:
            price = p.get("price", 0) or 0
            rating = p.get("rating", 0) or 0
            if min_price <= price <= max_price and rating >= min_rating:
                out.append(p)
        return out

    @staticmethod
    def _sort(products: list[dict], sort_by: str) -> list[dict]:
        key_fn, reverse = SORT_KEYS.get(sort_by, SORT_KEYS["price_asc"])
        return sorted(products, key=key_fn, reverse=reverse)

    @staticmethod
    def _flag_best_deal(products: list[dict]) -> dict | None:
        """
        Score products by value = rating / price (higher is better).
        Returns the top-scoring product or cheapest if no ratings exist.
        """
        if not products:
            return None
        scored = []
        for p in products:
            price = p.get("price", 0) or 0
            rating = p.get("rating", 0) or 0
            score = (rating / price) if price > 0 else 0
            scored.append((score, p))
        best = max(scored, key=lambda x: x[0])
        best[1]["is_best_deal"] = True
        return best[1]
