"""
models/alerts.py

Price-drop alert model and email notification engine.

When the current price of a tracked product drops below the user's
target_price, an email notification is sent via SMTP.

Usage (background job, e.g. APScheduler or Celery):
    from models.alerts import AlertModel
    AlertModel.check_all_alerts(current_prices_map)
"""

from __future__ import annotations

import datetime
import json
import logging
import os
import smtplib
import uuid
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

ALERTS_FILE = Path("data/alerts.json")
ALERTS_FILE.parent.mkdir(parents=True, exist_ok=True)


class AlertModel:
    """CRUD operations and notification delivery for price-drop alerts."""

    # ── CRUD ──────────────────────────────────────────────────────────────────

    @classmethod
    def create(
        cls,
        email: str,
        product_id: str,
        product_name: str,
        target_price: float,
        platform: str | None = None,
    ) -> dict:
        alert = {
            "id": str(uuid.uuid4()),
            "email": email,
            "product_id": product_id,
            "product_name": product_name,
            "target_price": target_price,
            "platform": platform,
            "active": True,
            "created_at": datetime.datetime.utcnow().isoformat(),
            "triggered_at": None,
        }
        alerts = cls._load()
        alerts.append(alert)
        cls._save(alerts)
        logger.info(f"Alert created: {alert['id']} for {email} @ ₹{target_price}")
        return alert

    @classmethod
    def list_for_email(cls, email: str) -> list[dict]:
        return [a for a in cls._load() if a["email"] == email]

    @classmethod
    def delete(cls, alert_id: str) -> bool:
        alerts = cls._load()
        new_alerts = [a for a in alerts if a["id"] != alert_id]
        if len(new_alerts) == len(alerts):
            return False
        cls._save(new_alerts)
        return True

    # ── Alert checker (run by scheduler) ─────────────────────────────────────

    @classmethod
    def check_all_alerts(cls, current_prices: dict[str, float]):
        """
        Evaluate all active alerts against current prices.
        Triggers email notifications for qualifying price drops.

        Args:
            current_prices: {product_id: current_price}
        """
        alerts = cls._load()
        triggered_ids = []

        for alert in alerts:
            if not alert.get("active"):
                continue
            product_id = alert["product_id"]
            current_price = current_prices.get(product_id)
            if current_price is None:
                continue
            if current_price <= alert["target_price"]:
                logger.info(
                    f"Alert triggered: {alert['id']} — "
                    f"current ₹{current_price} ≤ target ₹{alert['target_price']}"
                )
                cls._send_alert_email(alert, current_price)
                alert["active"] = False
                alert["triggered_at"] = datetime.datetime.utcnow().isoformat()
                triggered_ids.append(alert["id"])

        if triggered_ids:
            cls._save(alerts)
            logger.info(f"Deactivated {len(triggered_ids)} triggered alerts.")

    # ── Email delivery ─────────────────────────────────────────────────────────

    @classmethod
    def _send_alert_email(cls, alert: dict, current_price: float):
        smtp_host = os.getenv("SMTP_HOST", "smtp.gmail.com")
        smtp_port = int(os.getenv("SMTP_PORT", 587))
        smtp_user = os.getenv("SMTP_USER", "")
        smtp_pass = os.getenv("SMTP_PASS", "")

        if not smtp_user or not smtp_pass:
            logger.warning("SMTP not configured — skipping email alert.")
            return

        subject = f"🔔 Price Drop Alert: {alert['product_name']}"
        body_html = f"""
        <html><body style="font-family:sans-serif;max-width:600px;margin:auto;">
          <h2 style="color:#e94560;">PriceWise — Price Drop Alert!</h2>
          <p>Good news! The price of <strong>{alert['product_name']}</strong>
             has dropped to your target.</p>
          <table style="border-collapse:collapse;width:100%;">
            <tr><td style="padding:8px;background:#f4f4f4;"><b>Current Price</b></td>
                <td style="padding:8px;color:#27ae60;font-size:1.2em;"><b>₹{current_price:,.0f}</b></td></tr>
            <tr><td style="padding:8px;"><b>Your Target</b></td>
                <td style="padding:8px;">₹{alert['target_price']:,.0f}</td></tr>
            <tr><td style="padding:8px;background:#f4f4f4;"><b>Platform</b></td>
                <td style="padding:8px;">{alert.get('platform', 'N/A').title()}</td></tr>
          </table>
          <br>
          <a href="https://pricewise.app/search?q={alert['product_name']}"
             style="background:#e94560;color:#fff;padding:12px 24px;
                    border-radius:6px;text-decoration:none;display:inline-block;">
            View Deal →
          </a>
          <p style="color:#888;font-size:12px;margin-top:24px;">
            You're receiving this because you set a price alert on PriceWise.
          </p>
        </body></html>
        """

        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = smtp_user
        msg["To"] = alert["email"]
        msg.attach(MIMEText(body_html, "html"))

        try:
            with smtplib.SMTP(smtp_host, smtp_port) as server:
                server.ehlo()
                server.starttls()
                server.login(smtp_user, smtp_pass)
                server.sendmail(smtp_user, alert["email"], msg.as_string())
            logger.info(f"Alert email sent to {alert['email']}.")
        except Exception as exc:
            logger.error(f"Failed to send alert email: {exc}")

    # ── File persistence ───────────────────────────────────────────────────────

    @classmethod
    def _load(cls) -> list[dict]:
        if not ALERTS_FILE.exists():
            return []
        with open(ALERTS_FILE) as f:
            try:
                return json.load(f)
            except json.JSONDecodeError:
                return []

    @classmethod
    def _save(cls, alerts: list[dict]):
        with open(ALERTS_FILE, "w") as f:
            json.dump(alerts, f, indent=2)
