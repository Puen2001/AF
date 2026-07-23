"""Stage 1 — product discovery.

v1 sources: config/seed_products.yaml (always) + Shopee affiliate feed (TODO: wire
after the affiliate account exists). Seeds keep the pipeline unblocked forever.
"""
import json
from pathlib import Path

import yaml

from . import db

ROOT = Path(__file__).resolve().parent.parent


def ingest_seeds(conn) -> int:
    seed_file = ROOT / "config" / "seed_products.yaml"
    if not seed_file.exists():
        return 0
    added = 0
    for item in yaml.safe_load(seed_file.read_text()) or []:
        inserted = db.upsert_product(
            conn,
            source="seed",
            source_key=f"seed:{item['name']}",
            name=item["name"],
            category=item.get("category"),
            price_thb=item.get("price_thb"),
            url=item.get("url") or None,
            affiliate_link=item.get("affiliate_link") or None,
            facts=json.dumps(item.get("facts", []), ensure_ascii=False),
        )
        added += int(inserted)
    return added


def ingest_shopee_feed(conn) -> int:
    """TODO(phase 1.5): Shopee affiliate product/offer feed once SHOPEE_AFFILIATE_ID
    exists in config/secrets.env. Official affiliate API only — no scraping."""
    return 0


def run(conn) -> dict:
    return {"seeds_added": ingest_seeds(conn), "feed_added": ingest_shopee_feed(conn)}
