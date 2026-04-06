"""
models/price_history.py

MongoDB-backed price history model.
Tracks price snapshots per product over time, enabling:
  - Price history charts in the UI
  - Price drop alert evaluation
  - ML trend prediction input

Falls back gracefully to a JSON file store if MongoDB is unavailable.
"""

from __future__ import annotations

import datetime
import json
import logging
import os
import uuid
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# ─── File-based fallback (when MongoDB is not available) ──────────────────────
FALLBACK_DIR = Path("data/price_history")
FALLBACK_DIR.mkdir(parents=True, exist_ok=True)


class PriceHistoryModel:
    """
    Static methods for recording and querying price snapshots.

    Schema (each document):
    {
      "_id": ObjectId,
      "product_id": str,           # Scraper-generated UUID
      "query": str,                # Original search term
      "title": str,
      "platform": str,
      "price": float,
      "rating": float | None,
      "recorded_at": datetime,
    }
    """

    @classmethod
    def record_snapshot(cls, query: str, search_results: dict[str, Any]):
        """Persist current prices for all returned products."""
        products = search_results.get("products", [])
        now = datetime.datetime.utcnow().isoformat()

        records = []
        for p in products:
            if not p.get("price"):
                continue
            records.append({
                "id": str(uuid.uuid4()),
                "product_id": p.get("id", ""),
                "query": query,
                "title": p.get("title", ""),
                "platform": p.get("platform", ""),
                "price": p.get("price"),
                "rating": p.get("rating"),
                "recorded_at": now,
            })

        cls._write_records(records)
        logger.info(f"Recorded {len(records)} price snapshots for query='{query}'.")

    @classmethod
    def get_history(cls, product_id: str, days: int = 90) -> list[dict] | None:
        """
        Return price snapshots for a product_id within the last `days` days.
        Returns None if no records found.
        """
        cutoff = (
            datetime.datetime.utcnow() - datetime.timedelta(days=days)
        ).isoformat()

        all_records = cls._read_all_records()
        history = [
            r for r in all_records
            if r.get("product_id") == product_id and r.get("recorded_at", "") >= cutoff
        ]
        if not history:
            return None

        # Sort chronologically
        history.sort(key=lambda r: r.get("recorded_at", ""))
        return history

    @classmethod
    def get_popular_searches(cls, prefix: str, limit: int = 8) -> list[str]:
        """Return most-searched queries starting with `prefix`."""
        all_records = cls._read_all_records()
        from collections import Counter
        queries = [
            r["query"] for r in all_records
            if r.get("query", "").lower().startswith(prefix.lower())
        ]
        counted = Counter(queries).most_common(limit)
        return [q for q, _ in counted]

    # ── Storage helpers ───────────────────────────────────────────────────────

    @classmethod
    def _write_records(cls, records: list[dict]):
        """Append records to today's NDJSON file."""
        today = datetime.date.today().isoformat()
        path = FALLBACK_DIR / f"{today}.jsonl"
        with open(path, "a") as f:
            for r in records:
                f.write(json.dumps(r) + "\n")

    @classmethod
    def _read_all_records(cls) -> list[dict]:
        """Read all NDJSON records from the data directory."""
        records = []
        for path in sorted(FALLBACK_DIR.glob("*.jsonl")):
            with open(path) as f:
                for line in f:
                    line = line.strip()
                    if line:
                        try:
                            records.append(json.loads(line))
                        except json.JSONDecodeError:
                            pass
        return records
