"""Stage 0.5 — TOPIC FEASIBILITY GATE (the fix for "wrote the script, can't find footage").

TOGE insight: start from an interesting STORY that HAS footage, then attach a product as
the natural ending — not from a product you then stuff a story around. So before we spend
a script + render on a topic, we sketch its key visual beats and SCAN whether real footage
exists for them. Topics whose story can't be told in pictures are rejected up front.

Cheap by design: a beat with zero search results is infeasible (search-only, no download);
the single most-critical beat gets ONE real vision probe (footage.probe, no extract) to
confirm the story's core visual actually exists. Cost per topic ≈ 1 sketch call + a few
searches + 1 vision probe — far less than producing a doomed video.
"""
import json

from . import footage
from .llm import claude_p

SKETCH_PROMPT = """คุณคือ storyboard artist. เรื่องสั้นแนวสาระ/ชวนสงสัยเรื่องนี้:
หัวข้อ: {title}
มุมเล่า: {angle}
กระแสที่เกาะ: {trend}

เรื่องนี้ต้องใช้ "ภาพหลัก" (key visual beats) อะไรบ้างถึงจะเล่าได้ด้วยฟุตเทจจริง?
ให้ 3 ภาพที่สำคัญที่สุด เรียงจากสำคัญสุดก่อน — เป็น "วลีค้นหาฟุตเทจ" ภาษาอังกฤษที่เป็น
รูปธรรม เห็นภาพชัด (ไม่ใช่นามธรรม). ตัวอย่างที่ดี: "power bank battery swelling and smoking",
"airport security x-ray scanner bag". ตัวอย่างที่แย่ (นามธรรม): "technology", "danger".

ตอบ JSON เท่านั้น: {{"beats": ["...", "...", "..."]}}"""


def sketch_beats(topic, cfg) -> list[str]:
    """The 3 key visual beats the story needs, as concrete English footage queries."""
    try:
        r = claude_p(SKETCH_PROMPT.format(
            title=topic["title"], angle=topic["angle"] or "",
            trend=topic["trend"] or ""), cfg.get("model", "sonnet"))
        beats = [b.strip() for b in (r.get("beats") or []) if b and b.strip()]
        return beats[:3]
    except Exception:
        return []


def feasibility(topic, cfg) -> dict:
    """Footage-availability score in [0,1] for a topic's story.
    = (fraction of key beats that return search results)
      × (1.0 if the top beat is vision-confirmed to really exist, else 0.4 penalty)."""
    beats = sketch_beats(topic, cfg)
    if not beats:
        return {"score": 0.0, "beats": [], "searchable": 0, "total": 0,
                "confirmed": False}
    searchable = sum(1 for b in beats if footage._search([b], n=3))
    probe = footage.probe(beats[0])          # ONE real vision confirm on the core beat
    base = searchable / len(beats)
    score = base * (1.0 if probe.get("available") else 0.4)
    return {"score": round(score, 2), "beats": beats, "searchable": searchable,
            "total": len(beats), "confirmed": bool(probe.get("available")),
            "confirmed_seen": probe.get("seen")}


def rank(conn, cfg, topics, min_score: float = 0.5) -> list[dict]:
    """Score candidate topics by footage feasibility + audience fit, GATE out the
    stories the footage can't tell, and return them best-first. Product is not part
    of selection here — it is attached later as the natural ending (product = output)."""
    scored = []
    for t in topics:
        f = feasibility(t, cfg)
        combined = 0.65 * f["score"] + 0.35 * (float(t["audience_fit"] or 0) / 10.0)
        scored.append({"topic": t, "feasibility": f, "score": round(combined, 3)})
    scored.sort(key=lambda x: x["score"], reverse=True)
    passed = [s for s in scored if s["feasibility"]["score"] >= min_score]
    return passed or scored[:1]              # never return empty; worst-case best-effort
