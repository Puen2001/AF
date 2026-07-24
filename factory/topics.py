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


QUALIFY_PROMPT = """ประเมิน topic นี้สำหรับช่องสาระ-แกดเจ็ตไทยที่หารายได้ด้วย affiliate:
หัวข้อ: {title}
มุมเล่า: {angle}

ประเมิน:
1. affiliate_fit (0-1): เรื่องนี้โยงไปหา "สินค้า generic ที่กดลิงก์ affiliate Shopee ได้จริง"
   (แกดเจ็ต/ของใช้ราคา ฿100-900) ได้เนียนแค่ไหน — 1=โยงสินค้าได้ชัดเจน, 0=เรื่องวัฒนธรรม/ข่าว/
   คนดัง ที่โยงสินค้าไม่ได้เลย
2. product_hint: หมวดสินค้า generic ที่จะแนบได้ (ถ้ามี) ไม่มีให้เป็น ""
3. rights_safe (true/false): เรื่องนี้ "ไม่ได้" ต้องพึ่งภาพ/คลิป/ใบหน้าของคนดังหรือบุคคลเฉพาะ
   เจาะจง (เช่น Lisa, นักฟุตบอล/ดาราชื่อดัง, แบรนด์เฉพาะ) เป็นแกนหลักใช่ไหม —
   true=เล่าด้วยภาพทั่วไป/ของ/กลไกได้ ปลอดภัย, false=ต้องใช้ภาพคนดังเฉพาะ=เสี่ยงลิขสิทธิ์

ตอบ JSON เท่านั้น:
{{"affiliate_fit": 0-1, "product_hint": "...", "rights_safe": true/false, "reason": "สั้นๆ"}}"""


def qualify(topic, cfg) -> dict:
    """Cheap (no-WebSearch) gate: can this topic attach a real affiliate product, and is
    it free of specific-celebrity/rights risk? Run BEFORE the expensive footage probe."""
    try:
        r = claude_p(QUALIFY_PROMPT.format(title=topic["title"], angle=topic["angle"] or ""),
                     cfg.get("model", "sonnet"), timeout=120)
        return {"affiliate_fit": float(r.get("affiliate_fit", 0) or 0),
                "product_hint": (r.get("product_hint") or "").strip(),
                "rights_safe": bool(r.get("rights_safe", True)),
                "reason": r.get("reason", "")}
    except Exception:
        return {"affiliate_fit": 0.5, "product_hint": "", "rights_safe": True, "reason": "qualify failed"}


def rank(conn, cfg, topics, min_score: float = 0.5) -> list[dict]:
    """Pick a topic that is (1) rights-safe (no specific-celebrity footage), (2) leads to
    a real affiliate product, AND (3) tellable in footage. Cheap qualify gate runs first
    so we don't waste footage probes on topics we'd reject. Product is attached later as
    the natural ending (product = output)."""
    import sys
    scored = []
    for t in topics:
        q = qualify(t, cfg)
        if not q["rights_safe"]:
            print(f"[qualify] drop (celebrity/rights): {t['title'][:45]} — {q['reason'][:40]}",
                  file=sys.stderr, flush=True)
            continue
        if q["affiliate_fit"] < 0.3:
            print(f"[qualify] drop (no affiliate fit {q['affiliate_fit']}): {t['title'][:45]}",
                  file=sys.stderr, flush=True)
            continue
        f = feasibility(t, cfg)
        combined = (0.45 * f["score"] + 0.35 * q["affiliate_fit"]
                    + 0.20 * (float(t["audience_fit"] or 0) / 10.0))
        # promote the qualify product_hint if the topic didn't carry one
        if q["product_hint"] and not (t["product_hint"] or "").strip():
            conn.execute("UPDATE topics SET product_hint=? WHERE id=?",
                         (q["product_hint"], t["id"]))
            conn.commit()
        scored.append({"topic": t, "feasibility": f, "qualify": q,
                       "score": round(combined, 3)})
    scored.sort(key=lambda x: x["score"], reverse=True)
    passed = [s for s in scored if s["feasibility"]["score"] >= min_score]
    return passed or scored[:1] or []        # empty only if EVERY topic failed the gates
