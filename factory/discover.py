"""Stage 1 — product discovery.

v1 sources: config/seed_products.yaml (always) + Shopee affiliate feed (TODO: wire
after the affiliate account exists). Seeds keep the pipeline unblocked forever.
"""
import json
from pathlib import Path

import yaml

from . import db
from .llm import claude_p

ROOT = Path(__file__).resolve().parent.parent

TRIAGE_PROMPT = """คุณคือ content strategist วิดีโอสั้นสายแกดเจ็ตไทย ให้คะแนน "ศักยภาพคอนเทนต์"
ของสินค้าแต่ละชิ้น 1-10 (เกณฑ์: เล่าเป็นเรื่องน่าสงสัยได้แค่ไหน / คนแมสอินมั้ย /
ราคาเข้าถึงได้ / มีมุมที่คนยังไม่ค่อยรู้)

{listing}

ตอบเป็น JSON เท่านั้น: {{"scores": [{{"i": 0, "score": 7.5}}, ...]}}"""


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


def triage(conn, cfg) -> int:
    """Score unscored discovered products for content potential — best get produced first."""
    todo = conn.execute(
        "SELECT * FROM products WHERE status='discovered' AND score IS NULL "
        "ORDER BY id").fetchall()
    if not todo:
        return 0
    listing = "\n".join(
        f"{i}. {p['name']} (หมวด {p['category']}, ~{int(p['price_thb'] or 0)} บาท)"
        for i, p in enumerate(todo))
    try:
        result = claude_p(TRIAGE_PROMPT.format(listing=listing),
                          cfg.get("model", "sonnet"))
        for s in result.get("scores", []):
            p = todo[int(s["i"])]
            conn.execute("UPDATE products SET score=? WHERE id=?",
                         (float(s["score"]), p["id"]))
        conn.commit()
        return len(result.get("scores", []))
    except Exception:
        return 0  # unscored products still get produced, just unranked


def run(conn) -> dict:
    return {"seeds_added": ingest_seeds(conn), "feed_added": ingest_shopee_feed(conn)}
