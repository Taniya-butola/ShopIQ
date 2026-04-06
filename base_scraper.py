"""
scrapers/base_scraper.py

Abstract base class for all platform scrapers.
Provides:
  - Rotating user-agent pool
  - Retry logic with exponential backoff
  - Request rate limiting
  - CAPTCHA / block detection
  - Structured Product dataclass output
"""

from __future__ import annotations

import abc
import logging
import random
import time
import uuid
from dataclasses import dataclass, field, asdict
from typing import Any

import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

# ─── Realistic browser user-agent pool ────────────────────────────────────────
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:124.0) Gecko/20100101 Firefox/124.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_4_1) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Safari/605.1.15",
]

DEFAULT_HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
    "DNT": "1",
}


@dataclass
class Product:
    """Canonical product schema shared across all scrapers."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    title: str = ""
    price: float | None = None
    original_price: float | None = None          # Before discount
    currency: str = "INR"
    image_url: str = ""
    product_url: str = ""
    platform: str = ""
    rating: float | None = None
    review_count: int | None = None
    in_stock: bool = True
    discount_pct: float | None = None
    delivery_info: str = ""
    is_best_deal: bool = False
    relevance_score: float = 0.0
    scraped_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class BaseScraper(abc.ABC):
    """
    Abstract base for platform-specific scrapers.

    Subclasses must implement:
      - platform_name (property)
      - _build_search_url(query) → str
      - _parse_results(html) → list[Product]

    Provides shared HTTP session management with anti-blocking headers.
    """

    MAX_RETRIES = 3
    RETRY_BACKOFF = 2          # seconds; doubles on each retry
    REQUEST_DELAY = (1, 3)     # random sleep range between requests

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update(DEFAULT_HEADERS)
        self._rotate_ua()

    # ── Public API ────────────────────────────────────────────────────────────

    def search(self, query: str) -> list[dict]:
        """
        Execute a product search and return serialised Product dicts.
        Handles retries and anti-blocking measures.
        """
        url = self._build_search_url(query)
        html = self._fetch(url)
        if not html:
            logger.warning(f"[{self.platform_name}] Empty response for '{query}'")
            return []
        products = self._parse_results(html, query)
        logger.info(f"[{self.platform_name}] Parsed {len(products)} products.")
        return [p.to_dict() for p in products]

    # ── Abstract interface ─────────────────────────────────────────────────────

    @property
    @abc.abstractmethod
    def platform_name(self) -> str:
        """Human-readable platform identifier, e.g. 'amazon'."""

    @abc.abstractmethod
    def _build_search_url(self, query: str) -> str:
        """Return the search results URL for the given query."""

    @abc.abstractmethod
    def _parse_results(self, html: str, query: str) -> list[Product]:
        """Parse the HTML of a search results page into Product objects."""

    # ── Shared utilities ──────────────────────────────────────────────────────

    def _fetch(self, url: str) -> str | None:
        """
        GET `url` with retry logic, rotating UA, and backoff.
        Returns HTML string or None on failure.
        """
        self._rotate_ua()
        delay = random.uniform(*self.REQUEST_DELAY)
        time.sleep(delay)

        for attempt in range(1, self.MAX_RETRIES + 1):
            try:
                resp = self.session.get(url, timeout=15)
                if self._is_blocked(resp):
                    logger.warning(
                        f"[{self.platform_name}] Blocked (attempt {attempt}). "
                        "Rotating UA and sleeping."
                    )
                    self._rotate_ua()
                    time.sleep(self.RETRY_BACKOFF ** attempt)
                    continue
                resp.raise_for_status()
                return resp.text
            except requests.RequestException as exc:
                logger.warning(
                    f"[{self.platform_name}] Attempt {attempt} failed: {exc}"
                )
                if attempt < self.MAX_RETRIES:
                    time.sleep(self.RETRY_BACKOFF ** attempt)
        return None

    def _get_soup(self, html: str) -> BeautifulSoup:
        return BeautifulSoup(html, "html.parser")

    @staticmethod
    def _is_blocked(resp: requests.Response) -> bool:
        """Heuristic: detect CAPTCHA or block pages."""
        block_signals = [
            resp.status_code in (403, 429, 503),
            "captcha" in resp.text.lower(),
            "robot" in resp.text.lower(),
            "Access Denied" in resp.text,
            "Sorry, we just need to make sure" in resp.text,
        ]
        return any(block_signals)

    def _rotate_ua(self):
        """Pick a random user-agent from the pool."""
        self.session.headers["User-Agent"] = random.choice(USER_AGENTS)

    @staticmethod
    def _clean_price(raw: str) -> float | None:
        """Extract a numeric price from a string like '₹1,299.00'."""
        if not raw:
            return None
        cleaned = raw.replace(",", "").replace("₹", "").replace("$", "").strip()
        # Keep only digits and decimal point
        import re
        match = re.search(r"[\d]+\.?\d*", cleaned)
        return float(match.group()) if match else None

    @staticmethod
    def _clean_rating(raw: str) -> float | None:
        """Extract a float rating from strings like '4.2 out of 5'."""
        import re
        if not raw:
            return None
        match = re.search(r"[\d]+\.?\d*", raw)
        return float(match.group()) if match else None
