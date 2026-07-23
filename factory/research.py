"""Stage 1.5 — per-product web research brief (claude -p + WebSearch).

Upgrades story raw material from static seed facts to a verified, sourced brief:
tellable facts, popular misconceptions, what reviews praise/complain about, and
Thai-market context. Product-category level only (no brand claims) so the brief
stays reusable and the fact-check gate stays meaningful.
"""
import json

from . import db
from .llm import claude_p

RESEARCH_PROMPT = """คุณคือนักวิจัยคอนเทนต์วิดีโอสั้น ค้นเว็บเกี่ยวกับสินค้าประเภทนี้ แล้วสรุปเป็น brief:
สินค้า: {name} (หมวด {category}, ราคาไทยประมาณ {price} บาท)

ต้องการ:
- facts: 5-8 ข้อเท็จจริงที่ตรวจสอบได้และ "น่าเล่า" — เน้นสิ่งที่คนส่วนใหญ่ไม่รู้
  กลไกการทำงาน ตัวเลขที่จับต้องได้ การเปรียบเทียบที่เห็นภาพ (แต่ละข้อแนบ source URL)
- misconceptions: ความเข้าใจผิดยอดฮิตเกี่ยวกับของประเภทนี้ 1-3 ข้อ
- review_signals: สิ่งที่รีวิว (ประเภทสินค้านี้โดยรวม) ชมบ่อยและบ่นบ่อย
- th_context: ช่วงราคาตลาดไทย / บริบทความนิยมในไทย 1-2 ประโยค

กติกาเข้ม: ระดับประเภทสินค้าเท่านั้น ห้ามผูกแบรนด์/รุ่นเฉพาะ ห้ามเดา — ไม่แน่ใจให้ตัดทิ้ง

ตอบเป็น JSON เท่านั้น:
{{"facts": [{{"text": "...", "source": "url"}}],
  "misconceptions": ["..."],
  "review_signals": {{"praise": ["..."], "complaints": ["..."]}},
  "th_context": "..."}}"""


def ensure(conn, product, cfg) -> dict | None:
    """Return the product's research brief, running it once and caching in DB."""
    if product["research"]:
        return json.loads(product["research"])
    sg = cfg.get("scriptgen", {})
    try:
        brief = claude_p(
            RESEARCH_PROMPT.format(name=product["name"],
                                   category=product["category"] or "gadget",
                                   price=int(product["price_thb"] or 0)),
            sg.get("research_model", sg.get("model", cfg.get("model", "sonnet"))),
            tools="WebSearch", timeout=420)
    except Exception:
        return None  # pipeline degrades to seed facts, never blocks
    conn.execute("UPDATE products SET research=? WHERE id=?",
                 (json.dumps(brief, ensure_ascii=False), product["id"]))
    conn.commit()
    return brief
