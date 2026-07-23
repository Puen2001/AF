"""Orchestration — the showrunner. One control module, not an agent framework
(deliberate: the pipeline is linear and SQLite already owns state).

plan()    — daily: pick which products to produce and with which story angle,
            rotating angles/categories for variety (also the anti-mass-production
            compliance lever).
analyze() — weekly: state digest now; once posts+metrics rows exist, an LLM pass
            reads performance and returns insights + SEO/packaging recommendations
            (consumed by the phase-4 learning loop and the Telegram digest).
"""
import json

from . import db
from .llm import claude_p

PLAN_PROMPT = """คุณคือ showrunner ช่องวิดีโอสั้นสายแกดเจ็ตไทย วางแผนการผลิตวันนี้

คิวสินค้า (เรียงตามคะแนนศักยภาพ):
{queue}

มุมเล่า (angle) ที่ใช้ไปล่าสุด เรียงจากใหม่สุด: {recent_angles}
มุมเล่าที่มีให้เลือก: {angles}
โควตาวันนี้: {quota} คลิป

กติกา: เลือกสินค้าที่คะแนนสูงก่อน แต่สลับหมวดสินค้าและมุมเล่าไม่ให้ซ้ำกับคลิปล่าสุดๆ
(ความหลากหลายของโครงเรื่องคือทั้งคุณภาพและการกันโดนมองเป็นคอนเทนต์ปั๊ม)

ตอบเป็น JSON เท่านั้น:
{{"picks": [{{"product_id": <id>, "angle": "<angle>", "reason": "..."}}]}}"""

ANALYZE_PROMPT = """คุณคือนักวิเคราะห์ช่องวิดีโอสั้น อ่านข้อมูลผลงานแล้วสรุป:
1) คลิป/ฮุค/มุมเล่า/หมวดสินค้าแบบไหน perform ดี-แย่ เพราะอะไร (อิงตัวเลข)
2) คำแนะนำ SEO/แพ็กเกจจิ้ง (title/caption/hashtags) สำหรับสัปดาห์หน้า 2-3 ข้อ
3) ปรับ mix การผลิตยังไง (หมวด/มุมเล่า/ความยาว)

ข้อมูล:
{data}

ตอบเป็น JSON เท่านั้น:
{{"insights": ["..."], "seo_recommendations": ["..."], "production_changes": ["..."]}}"""


def plan(conn, cfg, quota: int) -> list[dict]:
    queue = db.rows(conn, "products", "discovered", limit=10,
                    order="score DESC, id")
    if not queue:
        return []
    recent = [r["hook_id"] for r in conn.execute(
        "SELECT hook_id FROM scripts ORDER BY id DESC LIMIT 7")]
    from .scriptgen import ANGLES
    listing = "\n".join(
        f"- id {p['id']}: {p['name']} (หมวด {p['category']}, "
        f"คะแนน {p['score'] if p['score'] is not None else '-'})" for p in queue)
    try:
        result = claude_p(PLAN_PROMPT.format(
            queue=listing, recent_angles=", ".join(recent) or "-",
            angles=", ".join(ANGLES), quota=quota), cfg.get("model", "sonnet"))
        valid_ids = {p["id"] for p in queue}
        return [p for p in result.get("picks", [])
                if p.get("product_id") in valid_ids][:quota]
    except Exception:
        return []  # run.py falls back to plain score order


def analyze(conn, cfg) -> dict:
    state = db.counts(conn)
    metrics = conn.execute(
        "SELECT p.platform, p.url, m.views, m.likes, m.clicks, m.commissions_thb, "
        "s.hook_id angle, pr.category, pr.name "
        "FROM metrics m JOIN posts p ON m.post_id=p.id "
        "JOIN videos v ON p.video_id=v.id JOIN scripts s ON v.script_id=s.id "
        "JOIN products pr ON s.product_id=pr.id "
        "ORDER BY m.captured_at DESC LIMIT 100").fetchall()
    if not metrics:
        return {"state": state,
                "note": "no performance data yet — analysis activates after first posts"}
    data = json.dumps([dict(r) for r in metrics], ensure_ascii=False)
    result = claude_p(ANALYZE_PROMPT.format(data=data), cfg.get("model", "sonnet"))
    return {"state": state, **result}
