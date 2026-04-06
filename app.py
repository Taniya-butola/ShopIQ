"""
PriceWise - E-commerce Price Comparison Engine
Main Flask Application Entry Point
"""

import os
import logging
from pathlib import Path

from flask import Flask, send_from_directory
from flask_cors import CORS
from dotenv import load_dotenv




# ─── Load environment variables ───────────────────────────────────────────────
load_dotenv()
from routes import api_bp

# ─── Logging configuration ────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("logs/app.log", mode="a"),
    ],
)
logger = logging.getLogger(__name__)


def create_app() -> Flask:
    """Application factory — creates and configures the Flask app."""
    base_dir = Path(__file__).resolve().parent
    app = Flask(__name__)

    # ── Config ────────────────────────────────────────────────────────────────
    app.config.update(
        SECRET_KEY=os.getenv("SECRET_KEY", "dev-secret-key-change-in-prod"),
        MONGO_URI=os.getenv("MONGO_URI", "mongodb://localhost:27017/pricewise"),
        CACHE_TTL=int(os.getenv("CACHE_TTL", 3600)),          # 1 hour default
        MAX_SCRAPERS=int(os.getenv("MAX_SCRAPERS", 5)),
        ALERT_EMAIL=os.getenv("ALERT_EMAIL", ""),
        SMTP_HOST=os.getenv("SMTP_HOST", "smtp.gmail.com"),
        SMTP_PORT=int(os.getenv("SMTP_PORT", 587)),
        SMTP_USER=os.getenv("SMTP_USER", ""),
        SMTP_PASS=os.getenv("SMTP_PASS", ""),
        OPENAI_API_KEY=os.getenv("OPENAI_API_KEY", ""),       # Optional: for ML features
        ENV=os.getenv("FLASK_ENV", "development"),
    )

    # ── Extensions ────────────────────────────────────────────────────────────
    CORS(app, resources={r"/api/*": {"origins": "*"}})

    # ── Database ──────────────────────────────────────────────────────────────
    

    # ── Blueprints ────────────────────────────────────────────────────────────
    app.register_blueprint(api_bp, url_prefix="/api")

    @app.route("/")
    def index():
        return send_from_directory(base_dir, "index.html")

    @app.route("/static/css/style.css")
    def style_css():
        return send_from_directory(base_dir, "style.css")

    @app.route("/static/js/app.js")
    def app_js():
        return send_from_directory(base_dir, "app.js")


    # ── Health check ──────────────────────────────────────────────────────────
    @app.route("/health")
    def health():
        return {"status": "ok", "service": "PriceWise API"}, 200

    logger.info("PriceWise app created successfully.")
    return app


if __name__ == "__main__":
    os.makedirs("logs", exist_ok=True)
    app = create_app()
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 5000)), debug=True)
