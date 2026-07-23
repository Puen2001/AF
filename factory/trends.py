"""Stage 0 (story-first) — trend → topic discovery.

Scans Thailand trends against the channel's audience profile and proposes
curiosity-led STORY topics (not products). Each topic may carry a product_hint
(a category that could fit the story) but attaching a product stays situational
and happens later, in scriptgen. Runs on `claude -p` + WebSearch.
"""
import json
from datetime import date, timedelta

from . import db
from .llm import claude_p


def _active_events(cfg, lookahead_days: int = 21) -> list[dict]:
    """Seasonal events whose run-window is open now or opens within lookahead_days,
    so content ships BEFORE the event. Windows are MM-DD..MM-DD (year-agnostic)."""
    today = date.today()
    horizon = today + timedelta(days=lookahead_days)
    out = []
    for ev in cfg.get("seasonal", []):
        try:
            a, b = ev["window"].split("..")
            for yr in (today.year, today.year + 1):
                start = date(yr, int(a[:2]), int(a[3:]))
                end = date(yr, int(b[:2]), int(b[3:]))
                if end < start:  # wraps year-end
                    end = date(yr + 1, int(b[:2]), int(b[3:]))
                if start <= horizon and today <= end:
                    out.append({"event": ev["event"], "hints": ev.get("hints", ""),
                                "starts": start.isoformat()})
                    break
        except Exception:
            continue
    return out

DISCOVER_PROMPT = """คุณคือครีเอทีฟช่องวิดีโอสั้นสายสาระ-ความรู้รอบตัวของไทย (แนวเดียวกับช่องดังที่เล่าเรื่องน่าทึ่ง
โดยไม่ขายของ) ค้นเทรนด์ไทยตอนนี้ แล้วเสนอ "หัวข้อเรื่องเล่า" ที่คนจะหยุดดู

แบรนด์/โทน: {identity} | เสียงเล่า: {voice}
คนดู: อายุ {age} — {who} | สนใจ: {interests}
แหล่งเทรนด์ที่ให้สแกน: {sources}

วันนี้: {today}
เทศกาล/ช่วงเวลาที่กำลังจะมาถึง (ควรทำคอนเทนต์ล่วงหน้าก่อนกระแสพีค): {events}

คลิปสั้น "outlier" ที่กำลังปังในหมวดนี้ (วิวเยอะทั้งที่ช่องเล็ก = เนื้อหาชนะ ทำซ้ำได้):
{outliers}
→ ใช้เป็นแรงบันดาลใจว่า "หัวข้อ/มุมแบบไหนกำลังเวิร์ก" แล้วเล่าเป็นเรื่องของเราเอง
  (ห้ามลอก ห้ามเอาคลิป/ฟุตเทจเขามาใช้ — เอาแค่ไอเดียหัวข้อที่พิสูจน์แล้วว่าปัง)

ค้นเว็บหาว่าอะไร "กำลังฮอต" ในไทยตอนนี้ แล้วเสนอ {n} หัวข้อที่ฮุคคนได้ — ให้มองหาโดยเฉพาะ:
- โมเมนต์วัฒนธรรม/ไวรัล: คนดัง ยูทูบเบอร์ ดารา นักกีฬา (เช่นตอน Speed มาไทย), อีเวนต์, มีม,
  เกม/หนัง/เพลงที่เพิ่งดัง, ดราม่าที่คนพูดถึง
- เทศกาล/ฤดูกาลที่กำลังจะมา (ข้างบน) — เล่าเรื่องล่วงหน้าให้คนเตรียมตัว เกาะช่วงที่คนเริ่มค้นหา
- เรื่องน่าทึ่ง/ความเข้าใจผิด/กลไกเบื้องหลัง ที่โยงเข้ากับโมเมนต์นั้นได้

แต่ละหัวข้อต้อง:
- เป็น "เรื่องเล่า" ที่เกาะกระแส ไม่ใช่รีวิวสินค้า
- **กติกาสำคัญ (กันโดนแบน/ฟ้อง)**: อ้างอิงกระแส/บุคคลสาธารณะแบบ "พูดถึง" ได้
  แต่ห้ามกุว่าคนดังเอนดอร์สสินค้า ห้ามใช้ภาพ/คลิป/ใบหน้าของเขาโดยไม่มีสิทธิ์
  เชื่อมได้แค่ระดับ "ประเภทของ/สิ่งที่เกี่ยวกับกระแสนั้น" ที่เป็นเรื่องจริงเท่านั้น
- product_hint: ถ้ามี "หมวดสินค้า" ที่แนบ affiliate ได้อย่างเนียนและจริง ให้ระบุ; ไม่มีก็เว้น ""
- hook_reason: ทำไมหัวข้อนี้จะหยุดนิ้วคนดูได้ (เกาะกระแสอะไร คนกำลังอินเรื่องนี้เพราะ?)

ตอบเป็น JSON เท่านั้น:
{{"topics": [
  {{"title": "เรื่องที่จะเล่า สั้นๆ", "angle": "มุมชวนสงสัย/ฮุค",
    "trend": "กระแส/คน/อีเวนต์ที่เกาะ", "hook_reason": "ทำไมถึงฮุค",
    "audience_fit": 1-10, "product_hint": "หมวดสินค้า หรือ ''"}}
]}}"""


def discover(conn, cfg) -> dict:
    if cfg.get("mode") != "story-first":
        return {"topics_added": 0, "skipped": "product-first mode"}
    br, au, tr = cfg.get("brand", {}), cfg.get("audience", {}), cfg.get("trends", {})
    events = _active_events(cfg)
    events_str = "; ".join(f"{e['event']} (สินค้าที่เกี่ยว: {e['hints']})"
                           for e in events) or "ไม่มีเทศกาลใกล้"
    outliers_str = "(ปิดการ mine)"
    if tr.get("mine_outliers", True):
        from . import outliers
        qs = tr.get("outlier_queries",
                    ["แกดเจ็ต gadget shorts", "ของมันต้องมี review shorts",
                     "รู้หรือไม่ เทคโนโลยี shorts"])
        outliers_str = outliers.as_signal(outliers.mine(qs))
    try:
        result = claude_p(DISCOVER_PROMPT.format(
            identity=br.get("identity", ""), voice=br.get("voice", ""),
            age=au.get("age", ""), who=au.get("who", ""),
            interests=", ".join(au.get("interests", [])),
            sources=", ".join(tr.get("sources", [])),
            today=date.today().isoformat(), events=events_str,
            outliers=outliers_str, n=tr.get("topics_per_run", 5)),
            cfg.get("model", "sonnet"), tools="WebSearch", timeout=420)
    except Exception as e:
        return {"topics_added": 0, "error": str(e)}
    added = 0
    for t in result.get("topics", []):
        title = (t.get("title") or "").strip()
        if not title:
            continue
        cur = conn.execute(
            "INSERT OR IGNORE INTO topics "
            "(source, source_key, title, angle, trend, audience_fit, product_hint, "
            "status, created_at) VALUES (?,?,?,?,?,?,?, 'discovered', ?)",
            ("trend", f"trend:{title}", title, t.get("angle"), t.get("trend"),
             float(t.get("audience_fit") or 0), (t.get("product_hint") or "").strip(),
             db.now()))
        added += cur.rowcount
    conn.commit()
    return {"topics_added": added}
