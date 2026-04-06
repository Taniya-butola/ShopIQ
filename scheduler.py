"""
utils/scheduler.py

Background job scheduler using APScheduler.
Runs the price-drop alert checker every 30 minutes.

To enable, call start_scheduler(app) in your app factory.

Usage:
    from utils.scheduler import start_scheduler
    start_scheduler(app)
"""

import logging
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger

logger = logging.getLogger(__name__)


def _check_alerts_job():
    """
    Periodically re-scrapes prices for all products that have active alerts,
    then evaluates each alert against the fresh prices.
    """
    from alerts import AlertModel
    from cache import CacheManager
    from demo_scraper import DemoScraper

    logger.info("[Scheduler] Running price alert check…")
    alerts = AlertModel._load()
    active = [a for a in alerts if a.get("active")]
    if not active:
        logger.info("[Scheduler] No active alerts — skipping.")
        return

    # Build a map of product_name → fresh price using the demo scraper
    # In production, route to the correct platform scraper per alert.
    current_prices: dict[str, float] = {}
    scraper = DemoScraper()

    for alert in active:
        query = alert.get("product_name", "")
        products = scraper.search(query)
        for p in products:
            if p.get("price"):
                pid = alert["product_id"]
                # Keep the lowest price seen across results
                current_prices[pid] = min(
                    current_prices.get(pid, float("inf")),
                    p["price"],
                )

    AlertModel.check_all_alerts(current_prices)
    logger.info(f"[Scheduler] Checked {len(active)} active alert(s).")


def start_scheduler(app):
    """Attach and start the background scheduler to the Flask app."""
    scheduler = BackgroundScheduler()
    scheduler.add_job(
        func=_check_alerts_job,
        trigger=IntervalTrigger(minutes=30),
        id="price_alert_check",
        name="Price Drop Alert Checker",
        replace_existing=True,
    )
    scheduler.start()
    app.extensions["scheduler"] = scheduler
    logger.info("[Scheduler] Background scheduler started (interval: 30 min).")

    # Shut down gracefully with the app
    import atexit
    atexit.register(lambda: scheduler.shutdown(wait=False))
