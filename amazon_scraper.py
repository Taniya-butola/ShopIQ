"""
scrapers/amazon_scraper.py

Amazon India search result scraper.

⚠️  IMPORTANT LEGAL NOTE:
    Scraping Amazon may violate their Terms of Service.
    In production, prefer the Amazon Product Advertising API (PA-API):
    https://affiliate-program.amazon.in/assoc_credentials/home

    This scraper is provided for educational purposes. Use responsibly.

Anti-blocking techniques used:
  - Rotating user-agents
  - Random delay between requests
  - Cookie persistence via session
  - Accept-Language: en-US to get consistent page structure
"""

import datetime
import logging
import re

from base_scraper import BaseScraper, Product

logger = logging.getLogger(__name__)

AMAZON_BASE = "https://www.amazon.in"


class AmazonScraper(BaseScraper):
    """Scrapes Amazon India product search results."""

    platform_name = "amazon"

    def _build_search_url(self, query: str) -> str:
        encoded = query.replace(" ", "+")
        return f"{AMAZON_BASE}/s?k={encoded}&ref=nb_sb_noss"

    def _parse_results(self, html: str, query: str) -> list[Product]:
        soup = self._get_soup(html)
        products: list[Product] = []

        # Amazon search result cards share this data-component-type attribute
        cards = soup.select("[data-component-type='s-search-result']")
        logger.debug(f"[amazon] Found {len(cards)} cards.")

        for card in cards[:12]:           # Limit to top 12 results
            try:
                product = self._parse_card(card)
                if product and product.price:
                    products.append(product)
            except Exception as exc:
                logger.debug(f"[amazon] Card parse error: {exc}")

        return products

    def _parse_card(self, card) -> Product | None:
        # ── Title ──────────────────────────────────────────────────────────────
        title_el = card.select_one("h2 a span")
        if not title_el:
            return None
        title = title_el.get_text(strip=True)

        # ── URL ────────────────────────────────────────────────────────────────
        link_el = card.select_one("h2 a")
        raw_url = link_el.get("href", "") if link_el else ""
        product_url = f"{AMAZON_BASE}{raw_url}" if raw_url.startswith("/") else raw_url

        # ── Price ──────────────────────────────────────────────────────────────
        price_el = card.select_one(".a-price .a-offscreen")
        price = self._clean_price(price_el.get_text() if price_el else "")

        # ── Original price (before discount) ──────────────────────────────────
        orig_el = card.select_one(".a-price.a-text-price .a-offscreen")
        original_price = self._clean_price(orig_el.get_text() if orig_el else "")

        # ── Discount % ────────────────────────────────────────────────────────
        discount_pct = None
        if price and original_price and original_price > price:
            discount_pct = round((original_price - price) / original_price * 100, 1)

        # ── Rating ────────────────────────────────────────────────────────────
        rating_el = card.select_one(".a-icon-alt")
        rating = self._clean_rating(rating_el.get_text() if rating_el else "")

        # ── Review count ──────────────────────────────────────────────────────
        review_el = card.select_one(".s-underline-text")
        review_count = None
        if review_el:
            raw = review_el.get_text(strip=True).replace(",", "")
            match = re.search(r"\d+", raw)
            review_count = int(match.group()) if match else None

        # ── Image ─────────────────────────────────────────────────────────────
        img_el = card.select_one("img.s-image")
        image_url = img_el.get("src", "") if img_el else ""

        # ── Prime / delivery ──────────────────────────────────────────────────
        delivery_info = ""
        prime_el = card.select_one(".s-prime")
        if prime_el:
            delivery_info = "Prime — Free Delivery"

        return Product(
            title=title,
            price=price,
            original_price=original_price,
            discount_pct=discount_pct,
            currency="INR",
            image_url=image_url,
            product_url=product_url,
            platform="amazon",
            rating=rating,
            review_count=review_count,
            delivery_info=delivery_info,
            scraped_at=datetime.datetime.utcnow().isoformat(),
        )
