"""
scrapers/flipkart_scraper.py

Flipkart India search result scraper.

⚠️  IMPORTANT LEGAL NOTE:
    Scraping Flipkart may violate their Terms of Service.
    Flipkart does not offer a public product API for general use.
    Some affiliates have access to Flipkart Affiliate API — prefer that when available.

    This scraper is for educational purposes.
"""

import datetime
import logging
import re

from base_scraper import BaseScraper, Product

logger = logging.getLogger(__name__)

FLIPKART_BASE = "https://www.flipkart.com"


class FlipkartScraper(BaseScraper):
    """Scrapes Flipkart India product search results."""

    platform_name = "flipkart"

    # Flipkart requires this cookie to skip the login prompt
    LOGIN_BYPASS = {"T": "0"}

    def __init__(self):
        super().__init__()
        self.session.cookies.update(self.LOGIN_BYPASS)

    def _build_search_url(self, query: str) -> str:
        encoded = query.replace(" ", "+")
        return f"{FLIPKART_BASE}/search?q={encoded}&otracker=search"

    def _parse_results(self, html: str, query: str) -> list[Product]:
        soup = self._get_soup(html)
        products: list[Product] = []

        # Flipkart uses multiple layout modes; try both selectors
        cards = (
            soup.select("div[data-id]") or
            soup.select("._1AtVbE") or
            soup.select("._13oc-S")
        )

        logger.debug(f"[flipkart] Found {len(cards)} cards.")

        for card in cards[:12]:
            try:
                product = self._parse_card(card)
                if product and product.price:
                    products.append(product)
            except Exception as exc:
                logger.debug(f"[flipkart] Card parse error: {exc}")

        return products

    def _parse_card(self, card) -> Product | None:
        # ── Title ──────────────────────────────────────────────────────────────
        title_el = (
            card.select_one("._4rR01T") or
            card.select_one(".IRpwTa") or
            card.select_one(".s1Q9rs") or
            card.select_one("a.IRpwTa")
        )
        if not title_el:
            return None
        title = title_el.get_text(strip=True)

        # ── URL ────────────────────────────────────────────────────────────────
        link_el = card.select_one("a[href]")
        raw_url = link_el.get("href", "") if link_el else ""
        product_url = (
            f"{FLIPKART_BASE}{raw_url}" if raw_url.startswith("/") else raw_url
        )

        # ── Price ──────────────────────────────────────────────────────────────
        price_el = card.select_one("._30jeq3") or card.select_one("._1_WHN1")
        price = self._clean_price(price_el.get_text() if price_el else "")

        # ── Original price ─────────────────────────────────────────────────────
        orig_el = card.select_one("._3I9_wc") or card.select_one("._27UcVY")
        original_price = self._clean_price(orig_el.get_text() if orig_el else "")

        # ── Discount ───────────────────────────────────────────────────────────
        disc_el = card.select_one("._3Ay6Sb") or card.select_one("._1oHLyA")
        discount_pct = None
        if disc_el:
            match = re.search(r"\d+", disc_el.get_text())
            discount_pct = float(match.group()) if match else None
        elif price and original_price and original_price > price:
            discount_pct = round((original_price - price) / original_price * 100, 1)

        # ── Rating ────────────────────────────────────────────────────────────
        rating_el = card.select_one("._3LWZlK") or card.select_one(".gUuXy-")
        rating = self._clean_rating(rating_el.get_text() if rating_el else "")

        # ── Review count ──────────────────────────────────────────────────────
        review_el = card.select_one("._2_R_DZ span") or card.select_one("._13vcmD")
        review_count = None
        if review_el:
            raw = review_el.get_text(strip=True).replace(",", "")
            match = re.search(r"\d+", raw)
            review_count = int(match.group()) if match else None

        # ── Image ─────────────────────────────────────────────────────────────
        img_el = card.select_one("img._396cs4") or card.select_one("img._2r_T1I")
        image_url = img_el.get("src", "") if img_el else ""

        # ── Free delivery ─────────────────────────────────────────────────────
        delivery_info = ""
        del_el = card.select_one("._3tcJ6v")
        if del_el:
            delivery_info = del_el.get_text(strip=True)

        return Product(
            title=title,
            price=price,
            original_price=original_price,
            discount_pct=discount_pct,
            currency="INR",
            image_url=image_url,
            product_url=product_url,
            platform="flipkart",
            rating=rating,
            review_count=review_count,
            delivery_info=delivery_info,
            scraped_at=datetime.datetime.utcnow().isoformat(),
        )
