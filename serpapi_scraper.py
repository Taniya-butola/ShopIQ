"""
Stable shopping search integration using SerpApi.

This scraper uses the Google Shopping engine via SerpApi instead of
direct scraping from marketplace websites. It is more reliable for
student/demo projects as long as a valid SERPAPI_API_KEY is configured.
"""

from __future__ import annotations

import datetime
import logging
import os

import requests

from base_scraper import Product

logger = logging.getLogger(__name__)


class SerpApiScraper:
    """Google Shopping search powered by SerpApi."""

    platform_name = "shopping"
    endpoint = "https://serpapi.com/search.json"

    def __init__(self):
        self.api_key = os.getenv("SERPAPI_API_KEY", "").strip()
        self.country = os.getenv("SERPAPI_GL", "in").strip() or "in"
        self.language = os.getenv("SERPAPI_HL", "en").strip() or "en"
        self.location = os.getenv("SERPAPI_LOCATION", "India").strip() or "India"

    def search(self, query: str) -> list[dict]:
        if not self.api_key:
            logger.warning("[serpapi] SERPAPI_API_KEY is not configured.")
            return []

        params = {
            "engine": "google_shopping",
            "q": query,
            "api_key": self.api_key,
            "gl": self.country,
            "hl": self.language,
            "location": self.location,
            "num": 12,
        }

        try:
            response = requests.get(self.endpoint, params=params, timeout=20)
            response.raise_for_status()
            payload = response.json()
        except requests.RequestException as exc:
            logger.warning(f"[serpapi] Request failed: {exc}")
            return []
        except ValueError as exc:
            logger.warning(f"[serpapi] Invalid JSON response: {exc}")
            return []

        results = payload.get("shopping_results", []) or []
        products: list[Product] = []

        for item in results:
            product = self._parse_item(item)
            if product and product.price:
                products.append(product)

        logger.info(f"[serpapi] Parsed {len(products)} products.")
        return [product.to_dict() for product in products]

    def _parse_item(self, item: dict) -> Product | None:
        title = item.get("title") or ""
        if not title:
            return None

        price = self._extract_price(item)
        original_price = self._extract_original_price(item)
        discount_pct = None
        if price and original_price and original_price > price:
            discount_pct = round((original_price - price) / original_price * 100, 1)

        source = item.get("source") or item.get("merchant") or "Shopping"
        product_url = (
            item.get("product_link")
            or item.get("link")
            or item.get("serpapi_product_api")
            or "#"
        )
        image_url = item.get("thumbnail") or item.get("thumbnails", [None])[0] or ""

        return Product(
            title=title,
            price=price,
            original_price=original_price,
            discount_pct=discount_pct,
            currency="INR",
            image_url=image_url,
            product_url=product_url,
            platform=self._normalise_source(source),
            rating=self._extract_rating(item),
            review_count=self._extract_review_count(item),
            delivery_info=item.get("delivery") or item.get("extensions", [None])[-1] or "",
            scraped_at=datetime.datetime.utcnow().isoformat(),
        )

    @staticmethod
    def _extract_price(item: dict) -> float | None:
        value = item.get("extracted_price")
        if value is not None:
            return float(value)

        raw = item.get("price")
        if not raw:
            return None
        return SerpApiScraper._clean_number(raw)

    @staticmethod
    def _extract_original_price(item: dict) -> float | None:
        value = item.get("extracted_old_price")
        if value is not None:
            return float(value)

        raw = item.get("old_price")
        if not raw:
            return None
        return SerpApiScraper._clean_number(raw)

    @staticmethod
    def _extract_rating(item: dict) -> float | None:
        value = item.get("rating")
        if value is None:
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _extract_review_count(item: dict) -> int | None:
        value = item.get("reviews")
        if value is None:
            return None
        try:
            return int(str(value).replace(",", "").strip())
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _clean_number(raw: str) -> float | None:
        cleaned = (
            str(raw)
            .replace("₹", "")
            .replace(",", "")
            .replace("$", "")
            .strip()
        )
        digits = []
        dot_seen = False
        for char in cleaned:
            if char.isdigit():
                digits.append(char)
            elif char == "." and not dot_seen:
                digits.append(char)
                dot_seen = True

        if not digits:
            return None

        try:
            return float("".join(digits))
        except ValueError:
            return None

    @staticmethod
    def _normalise_source(source: str) -> str:
        slug = source.lower().strip()
        slug = "".join(ch if ch.isalnum() else "-" for ch in slug)
        slug = "-".join(part for part in slug.split("-") if part)
        return slug or "shopping"
