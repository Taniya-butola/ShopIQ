"""
scrapers/demo_scraper.py

Demo / mock scraper that returns realistic product data without
making any real HTTP requests. This is the SAFE fallback:

  1. Use during development when you don't want to trigger real scrapers.
  2. Use in automated tests.
  3. Use to demo the UI without scraping-related rate limits.

It simulates realistic pricing variability per search query so the
comparison UI always has something interesting to display.
"""

from __future__ import annotations

import datetime
import hashlib
import random
from urllib.parse import quote
import uuid

from base_scraper import BaseScraper, Product

# ─── Sample product templates ─────────────────────────────────────────────────
PRODUCT_TEMPLATES = [
    {
        "title": "{query} - Premium Edition",
        "base_price": 1499,
        "rating": 4.3,
        "reviews": 2847,
        "image_bg": "#DBEAFE",
        "delivery": "Free Delivery by Tomorrow",
    },
    {
        "title": "{query} Pro Max Ultra",
        "base_price": 2199,
        "rating": 4.6,
        "reviews": 1203,
        "image_bg": "#E0F2FE",
        "delivery": "Prime — Same Day Delivery",
    },
    {
        "title": "{query} | Bestseller | Pack of 1",
        "base_price": 899,
        "rating": 4.1,
        "reviews": 5619,
        "image_bg": "#DCFCE7",
        "delivery": "Free Delivery in 2-3 Days",
    },
    {
        "title": "Original {query} — Official Store",
        "base_price": 1899,
        "rating": 4.5,
        "reviews": 931,
        "image_bg": "#FCE7F3",
        "delivery": "Assured Delivery",
    },
    {
        "title": "{query} (Limited Stock)",
        "base_price": 1199,
        "rating": 3.9,
        "reviews": 412,
        "image_bg": "#FDE68A",
        "delivery": "Delivery in 4-6 Days",
    },
    {
        "title": "{query} — Value Pack",
        "base_price": 749,
        "rating": 4.0,
        "reviews": 7823,
        "image_bg": "#FBCFE8",
        "delivery": "Free Delivery",
    },
]


class DemoScraper(BaseScraper):
    """
    Mock scraper that returns seeded-random product data.
    Results are deterministic per query string (seed from hash),
    so repeated searches for the same query return the same products.
    """

    platform_name = "demo"

    def search(self, query: str) -> list[dict]:
        """Override — no HTTP needed."""
        products = self._generate_products(query)
        return [p.to_dict() for p in products]

    # ── Required abstract implementations (not used) ──────────────────────────

    def _build_search_url(self, query: str) -> str:
        return f"https://demo.pricewise.local/search?q={query}"

    def _parse_results(self, html: str, query: str) -> list[Product]:
        return []   # Not used — search() is overridden

    # ── Mock data generation ──────────────────────────────────────────────────

    def _generate_products(self, query: str) -> list[Product]:
        # Seed random with a hash of the query for deterministic output
        seed = int(hashlib.md5(query.encode()).hexdigest(), 16) % (2 ** 31)
        rng = random.Random(seed)

        products = []
        templates = rng.sample(PRODUCT_TEMPLATES, k=min(len(PRODUCT_TEMPLATES), 6))

        for i, tmpl in enumerate(templates):
            # Vary price ±20 % to simulate real market
            price_factor = rng.uniform(0.80, 1.20)
            base_price = tmpl["base_price"] * price_factor
            price = round(base_price, -1)             # round to nearest 10
            original_price = round(price * rng.uniform(1.10, 1.40), -1)
            discount_pct = round((original_price - price) / original_price * 100, 1)

            title = tmpl["title"].replace("{query}", query.title())
            product_url = "#"

            products.append(
                Product(
                    id=str(uuid.uuid4()),
                    title=title,
                    price=price,
                    original_price=original_price,
                    discount_pct=discount_pct,
                    currency="INR",
                    image_url=self._build_demo_image(title, tmpl["image_bg"]),
                    product_url=product_url,
                    platform="demo",
                    rating=round(tmpl["rating"] + rng.uniform(-0.3, 0.3), 1),
                    review_count=tmpl["reviews"] + rng.randint(-100, 500),
                    in_stock=rng.random() > 0.1,      # 90 % in stock
                    delivery_info=tmpl["delivery"],
                    scraped_at=datetime.datetime.utcnow().isoformat(),
                )
            )

        return products

    @staticmethod
    def _build_demo_image(title: str, bg_color: str) -> str:
        label = (title[:26] + "...") if len(title) > 29 else title
        svg = f"""
        <svg xmlns='http://www.w3.org/2000/svg' width='400' height='400' viewBox='0 0 400 400'>
          <rect width='400' height='400' rx='36' fill='{bg_color}' />
          <rect x='70' y='62' width='260' height='188' rx='24' fill='#FFFFFF' opacity='0.92' />
          <circle cx='200' cy='156' r='58' fill='#2563EB' opacity='0.16' />
          <path d='M170 140h60v32h-60z' fill='#2563EB' opacity='0.78' />
          <rect x='100' y='282' width='200' height='18' rx='9' fill='#2563EB' opacity='0.18' />
          <text x='200' y='330' text-anchor='middle' font-size='24' font-family='Arial, sans-serif' fill='#0F172A'>{label}</text>
          <text x='200' y='102' text-anchor='middle' font-size='20' font-family='Arial, sans-serif' fill='#2563EB'>SHOPIQ Demo</text>
        </svg>
        """.strip()
        return f"data:image/svg+xml;charset=UTF-8,{quote(svg)}"
