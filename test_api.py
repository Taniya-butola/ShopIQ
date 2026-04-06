"""
tests/test_api.py — Automated tests for PriceWise API endpoints.

Run with: pytest tests/ -v
"""

import json
import sys
import os

# Ensure backend is on the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from app import create_app


@pytest.fixture
def client():
    app = create_app()
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


# ─── Health ───────────────────────────────────────────────────────────────────
def test_health(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    data = json.loads(resp.data)
    assert data["status"] == "ok"


# ─── Search ───────────────────────────────────────────────────────────────────
def test_search_missing_query(client):
    resp = client.get("/api/search")
    assert resp.status_code == 400
    data = json.loads(resp.data)
    assert not data["success"]


def test_search_demo_platform(client):
    resp = client.get("/api/search?q=laptop&platforms=demo")
    assert resp.status_code == 200
    data = json.loads(resp.data)
    assert data["success"]
    assert "products" in data["data"]
    assert len(data["data"]["products"]) > 0


def test_search_returns_prices(client):
    resp = client.get("/api/search?q=headphones&platforms=demo")
    data = json.loads(resp.data)
    products = data["data"]["products"]
    for p in products:
        assert p["price"] is not None
        assert p["price"] > 0


def test_search_sort_price_asc(client):
    resp = client.get("/api/search?q=phone&platforms=demo&sort=price_asc")
    data = json.loads(resp.data)
    prices = [p["price"] for p in data["data"]["products"]]
    assert prices == sorted(prices)


def test_search_sort_price_desc(client):
    resp = client.get("/api/search?q=phone&platforms=demo&sort=price_desc")
    data = json.loads(resp.data)
    prices = [p["price"] for p in data["data"]["products"]]
    assert prices == sorted(prices, reverse=True)


def test_search_min_price_filter(client):
    resp = client.get("/api/search?q=shoes&platforms=demo&min_price=1000")
    data = json.loads(resp.data)
    for p in data["data"]["products"]:
        assert p["price"] >= 1000


def test_search_max_price_filter(client):
    resp = client.get("/api/search?q=shoes&platforms=demo&max_price=1500")
    data = json.loads(resp.data)
    for p in data["data"]["products"]:
        assert p["price"] <= 1500


def test_search_caching(client):
    # First call: live
    resp1 = client.get("/api/search?q=keyboard&platforms=demo")
    data1 = json.loads(resp1.data)
    assert data1["source"] == "live"

    # Second call: cached
    resp2 = client.get("/api/search?q=keyboard&platforms=demo")
    data2 = json.loads(resp2.data)
    assert data2["source"] == "cache"


def test_search_invalid_price_param(client):
    resp = client.get("/api/search?q=test&min_price=abc")
    assert resp.status_code == 400


# ─── Alerts ───────────────────────────────────────────────────────────────────
def test_create_alert_missing_fields(client):
    resp = client.post(
        "/api/alerts",
        data=json.dumps({"email": "test@test.com"}),
        content_type="application/json",
    )
    assert resp.status_code == 400


def test_create_alert_success(client):
    payload = {
        "email": "test@example.com",
        "product_id": "abc-123",
        "product_name": "Test Product",
        "target_price": 999,
    }
    resp = client.post(
        "/api/alerts",
        data=json.dumps(payload),
        content_type="application/json",
    )
    assert resp.status_code == 201
    data = json.loads(resp.data)
    assert data["success"]
    assert data["data"]["email"] == "test@example.com"
    assert data["data"]["active"] is True


def test_list_alerts_requires_email(client):
    resp = client.get("/api/alerts")
    assert resp.status_code == 400


def test_list_alerts_for_email(client):
    email = "list-test@example.com"
    # Create one first
    client.post(
        "/api/alerts",
        data=json.dumps({
            "email": email,
            "product_id": "xyz",
            "product_name": "Widget",
            "target_price": 500,
        }),
        content_type="application/json",
    )
    resp = client.get(f"/api/alerts?email={email}")
    data = json.loads(resp.data)
    assert data["success"]
    assert any(a["email"] == email for a in data["data"])


# ─── Suggest ──────────────────────────────────────────────────────────────────
def test_suggest_short_query(client):
    resp = client.get("/api/suggest?q=a")
    data = json.loads(resp.data)
    assert data["success"]
    assert data["data"] == []   # Too short


# ─── Deal Suggester (unit) ────────────────────────────────────────────────────
def test_deal_suggester_logic():
    from deal_suggester import suggest_best_deal

    mock_results = {
        "products": [
            {"id": "1", "title": "Cheap Widget", "price": 500, "rating": 4.0,
             "discount_pct": 10, "review_count": 500},
            {"id": "2", "title": "Great Widget", "price": 800, "rating": 4.8,
             "discount_pct": 30, "review_count": 5000},
            {"id": "3", "title": "Meh Widget", "price": 1200, "rating": 3.5,
             "discount_pct": 5, "review_count": 100},
        ]
    }
    result = suggest_best_deal(mock_results)
    assert "product" in result
    assert "reasoning" in result
    assert result["product"]["id"] in ["1", "2", "3"]


# ─── Scraper unit tests ────────────────────────────────────────────────────────
def test_demo_scraper_returns_products():
    from demo_scraper import DemoScraper
    scraper = DemoScraper()
    results = scraper.search("iPhone")
    assert len(results) > 0
    for r in results:
        assert r["price"] > 0
        assert r["title"]
        assert r["platform"] == "demo"


def test_demo_scraper_deterministic():
    from demo_scraper import DemoScraper
    s = DemoScraper()
    r1 = s.search("Sony headphones")
    r2 = s.search("Sony headphones")
    assert [p["price"] for p in r1] == [p["price"] for p in r2]


def test_base_scraper_clean_price():
    from base_scraper import BaseScraper

    class _Stub(BaseScraper):
        platform_name = "stub"
        def _build_search_url(self, q): return ""
        def _parse_results(self, h, q): return []

    s = _Stub()
    assert s._clean_price("₹1,299.00") == 1299.0
    assert s._clean_price("$49.99") == 49.99
    assert s._clean_price("") is None
    assert s._clean_price("N/A") is None
