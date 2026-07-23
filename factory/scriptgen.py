"""Stage 2 — script generation via `claude -p` (headless), quality-ladder flow.

Per product: N drafts from distinct story angles → judge picks winner + names
weaknesses → polish rewrite (higher model) → strict fact-check (with one
revise-and-recheck cycle). Headless calls bill the metered automation credit,
not interactive session limits; write/judge run on a cheap model, polish on a
strong one.
"""
import json
import random
from pathlib import Path

from . import db, research
from .llm import claude_p

ROOT = Path(__file__).resolve().parent.parent

ANGLES = {
    "myth-bust": "หักล้างความเชื่อผิดๆ ที่คนส่วนใหญ่เข้าใจเกี่ยวกับของประเภทนี้",
    "hidden-feature": "เปิดเผยความสามารถ/กลไกที่คนใช้ของประเภทนี้ส่วนใหญ่ไม่รู้",
    "problem-solve": "เริ่มจาก pain point ในชีวิตประจำวันที่คนดูเจอเอง แล้วคลี่ว่าของชิ้นนี้แก้ยังไง",
    "price-surprise": "ความคุ้ม/ราคาที่สวนทางกับสิ่งที่คนคาด",
    "everyday-scene": "เล่าผ่านฉากในชีวิตจริงที่คนดูเห็นภาพตัวเองทันที",
}

WRITE_PROMPT = """คุณคือครีเอเตอร์วิดีโอสั้นสาย tech ภาษาไทย ที่คนดูค้างจนจบคลิปเป็นประจำ
เขียนสคริปต์ 1 เวอร์ชัน สำหรับสินค้านี้ ด้วยมุมเล่า (angle): {angle_desc}

สินค้า: {name} (หมวด {category}, ราคาประมาณ {price} บาท)
ข้อเท็จจริงที่ใช้ได้ (ห้ามอ้างเกินนี้ นอกจากความรู้ทั่วไปที่ถูกต้องของสินค้าประเภทนี้):
{facts}
{research_block}
กติกาการเล่าเรื่อง (retention rules — บังคับ):
- ฮุคต้องสร้าง "ช่องว่างความอยากรู้" ที่เฉพาะเจาะจง ไม่ใช่คำถามกว้างๆ — คนดูต้องรู้สึกว่าถ้าเลื่อนผ่านจะพลาดอะไรบางอย่าง
- ข้อเท็จจริงที่น่าสนใจที่สุด ต้องมาภายใน 2 ประโยคแรกหลังฮุค ห้ามเกริ่น
- ต้องมีจุดหักมุม/เซอร์ไพรส์ 1 จุด กลางเรื่อง (เช่น "แต่ที่คนส่วนใหญ่ไม่รู้คือ...")
- เปรียบเทียบให้เห็นภาพด้วยของใกล้ตัว อย่างน้อย 1 ครั้ง (เช่น "เล็กกว่าบัตรเครดิต")
- จบด้วย payoff ที่ตอบฮุค (วนกลับเชื่อมฮุคให้เล่นซ้ำได้ลื่น) แล้วค่อย CTA เบาๆ ("{cta}") — ห้ามขายของ ห้าม superlative
- ความยาวพูดรวม {wmin}-{wmax} คำ (20-40 วินาที)

ภาษา: ไทยภาษาพูดจริงๆ ประโยคสั้น จังหวะเหมือนเล่าให้เพื่อนฟัง ไม่มีภาษาเขียน
ไม่มีคำฟุ่มเฟือย ไม่ใส่ครับ/ค่ะ ห้ามฟังดูเป็นโฆษณาเด็ดขาด

ตอบเป็น JSON เท่านั้น ห้ามมีข้อความอื่น:
{{"hook": "...", "lines": ["ประโยคที่ 1", "..."],
  "caption": "แคปชันสั้นชวนคุย ลงท้ายด้วย: {disclosure}",
  "hashtags": ["#...", "#...", "#..."]}}"""

JUDGE_PROMPT = """คุณคือ editor วิดีโอสั้นที่เข้มงวดเรื่อง retention ให้คะแนนดราฟต์สคริปต์ต่อไปนี้
เกณฑ์ (1-10 ต่อข้อ): (a) ฮุคหยุดนิ้วได้จริง (b) อยากดูต่อถึงวินาทีสุดท้าย
(c) เนียน ไม่มีกลิ่นโฆษณา (d) ภาษาพูดธรรมชาติ อ่านออกเสียงลื่น (e) ข้อเท็จจริงน่าจดจำ

{drafts}

ตอบเป็น JSON เท่านั้น:
{{"best": <หมายเลขดราฟต์ที่ดีที่สุด เริ่มจาก 0>, "scores": [[a,b,c,d,e], ...],
  "notes": ["จุดที่ดราฟต์ผู้ชนะต้องแก้ 2-3 ข้อ เฉพาะเจาะจง"]}}"""

POLISH_PROMPT = """นี่คือดราฟต์สคริปต์วิดีโอสั้นที่ชนะการคัดเลือก และจุดอ่อนที่ editor ระบุ
เขียนเวอร์ชันสุดท้าย: แก้ทุกจุดอ่อน เหลาทุกประโยคให้คมและสั้นลงถ้าทำได้
คงโครงเรื่องและข้อเท็จจริงเดิม ห้ามเติมข้อเท็จจริงใหม่ ความยาว {wmin}-{wmax} คำ
ภาษาพูดธรรมชาติ ไม่ใส่ครับ/ค่ะ ห้ามกลิ่นโฆษณา

จุดอ่อนที่ต้องแก้:
{notes}

ดราฟต์ (JSON):
{body}

ตอบเป็น JSON โครงเดียวกันเท่านั้น ห้ามมีข้อความอื่น"""

CHECK_PROMPT = """ตรวจสอบสคริปต์วิดีโอสั้นนี้ สินค้า: {name} ราคาประมาณ {price} บาท

ข้อเท็จจริงที่อนุญาต:
{facts}

เกณฑ์ — "fail" เฉพาะเมื่อเจอ:
- ตัวเลขสเปก/ตัวเลขวัดผลที่ไม่อยู่ในลิสต์และไม่ใช่ราคาข้างต้น
- คำอวดอ้างเปรียบเทียบ ("ดีที่สุด", "อันดับ 1", "ถูกที่สุด")
- การการันตีผลลัพธ์ หรือสรรพคุณเฉพาะรุ่นที่ไม่อยู่ในลิสต์

เกณฑ์ — สิ่งเหล่านี้ "ผ่าน" ได้:
- การพูดถึงราคาแบบคร่าวๆ ที่สอดคล้องกับราคาข้างต้น (เช่น "หลักร้อย")
- ความรู้ทั่วไปที่ถูกต้องเกี่ยวกับสินค้าประเภทนี้ (เช่น สมาร์ทปลั๊กเสียบปลั๊กบ้านปกติได้)
- ภาษาพูด/การเปรียบเทียบเชิงสำนวนที่ไม่ได้บิดเบือนข้อเท็จจริง

สคริปต์:
{script}

ตอบเป็น JSON เท่านั้น: {{"verdict": "pass" หรือ "fail", "issues": ["..."]}}"""

REVISE_PROMPT = """สคริปต์วิดีโอสั้นนี้ไม่ผ่านการตรวจข้อเท็จจริง แก้เฉพาะประเด็นที่ระบุ
คงสไตล์ ความยาว และโครงเดิมไว้ ห้ามเติมสรรพคุณใหม่

ประเด็นที่ต้องแก้:
{issues}

สคริปต์เดิม (JSON):
{body}

ตอบเป็น JSON โครงเดียวกับสคริปต์เดิมเท่านั้น ห้ามมีข้อความอื่น"""


SHOTS_PROMPT = """คุณคือ editor วางภาพ (shot list) ให้วิดีโอสั้น — ภาพต้อง "เล่าเรื่อง" ตามที่พูด
สคริปต์ (line 0 คือฮุค, ที่เหลือคือเนื้อเรื่องตามลำดับ):
{numbered_lines}
สินค้าหลักในคลิป (ถ้ามี): {subject}

กติกาภาพ (บังคับ — นี่คือหัวใจ):
1. ภาพต้องตรงกับ "คำนาม/กริยาจริง" ในประโยคนั้น ไม่ใช่ภาพ mood กว้างๆ
   (พูด "แบตบวม" → โชว์แบตบวม, พูด "ตรา 3C" → โชว์ป้ายรับรอง, ไม่ใช่ภาพเครื่องบินลอยๆ)
2. **ต้องโชว์ตัวสินค้าจริง** อย่างน้อยที่: ช็อตแรก (ฮุค — โชว์สินค้ากำลังทำงาน/ผลลัพธ์),
   ช่วงกลาง 1 ครั้ง, และช็อตปิด (CTA). ห้ามมี 2 บรรทัดติดกันที่ไม่มีสินค้า/บริบทตรงของสินค้า
3. ช็อตฮุคห้ามเป็นภาพ establishing/mood — ต้องเป็นสินค้ากำลังใช้งานหรือภาพที่สะดุด
4. query = ภาษาอังกฤษเฉพาะเจาะจง เห็นภาพจริง (เช่น "power bank charging phone closeup",
   "hand holding power bank 3C label macro") ไม่ใช่ "technology"
5. type="product" = โชว์ตัวสินค้า, "context" = ภาพประกอบเรื่อง. ต้องมี product ≥ 2 ช็อต

ตอบเป็น JSON เท่านั้น (3-6 ช็อต):
{{"shots": [{{"from": 0, "to": 1, "query": "...", "type": "product|context"}}]}}"""

TOPIC_WRITE_PROMPT = """คุณคือครีเอเตอร์วิดีโอสั้นสายสาระ-ความรู้ไทย ที่คนดูค้างจนจบเป็นประจำ
เขียนสคริปต์ 1 เวอร์ชัน เล่า "เรื่อง" นี้ ด้วยมุมเล่า (angle): {angle_desc}

เรื่องที่จะเล่า: {title}
มุมหลัก: {angle}
ข้อเท็จจริงที่ใช้ได้ (ห้ามอ้างเกินนี้ นอกจากความรู้ทั่วไปที่ถูกต้อง):
{facts}
{research_block}
กติกาการเล่าเรื่อง (retention rules — บังคับ):
- ฮุคต้องสร้าง "ช่องว่างความอยากรู้" เฉพาะเจาะจง คนดูต้องรู้สึกว่าเลื่อนผ่านแล้วพลาด
- ข้อเท็จจริงที่น่าสนใจที่สุดมาภายใน 2 ประโยคแรกหลังฮุค ห้ามเกริ่น
- มีจุดหักมุม/เซอร์ไพรส์ 1 จุด กลางเรื่อง
- เปรียบเทียบเห็นภาพด้วยของใกล้ตัว อย่างน้อย 1 ครั้ง
- จบด้วย payoff ที่ตอบฮุค — นี่คือ "เรื่องเล่า" ไม่ใช่โฆษณา ห้ามขายของในตัวสคริปต์นี้
  (การแนบสินค้าเป็นขั้นตอนแยกทีหลัง ถ้าเรื่องนี้เหมาะ)
- **loop close**: ประโยคสุดท้ายต้องวนกลับไปเชื่อมกับฮุค ให้เวลาเล่นซ้ำแล้วรู้สึกต่อเนื่อง/อยากดูอีกรอบ
  (YouTube นับการเล่นซ้ำเป็นวิว การปิดแบบวนช่วยดันคลิปโดยตรง)
- ถ้าเรื่องเกาะกระแสคนดัง/บุคคลสาธารณะ: "พูดถึง" ได้ แต่ห้ามกุว่าเขาเอนดอร์สหรือใช้สินค้า
  ห้ามอ้างคำพูด/การกระทำที่ไม่เป็นความจริง เชื่อมได้แค่ข้อเท็จจริงสาธารณะที่ตรวจสอบได้
- ความยาวพูดรวม {wmin}-{wmax} คำ (20-40 วินาที)

ภาษา: ไทยพูดจริง ประโยคสั้น จังหวะเล่าให้เพื่อนฟัง ไม่มีภาษาเขียน ไม่ใส่ครับ/ค่ะ

ตอบเป็น JSON เท่านั้น:
{{"hook": "...", "lines": ["ประโยคที่ 1", "..."],
  "caption": "แคปชันสั้นชวนคุย", "hashtags": ["#...", "#...", "#..."]}}"""

PRODUCT_MATCH_PROMPT = """เรื่องเล่านี้จบแล้ว ตัดสินใจว่าควร "แนบสินค้า affiliate แบบเนียนๆ" ตอนท้ายหรือไม่
เกณฑ์: แนบเฉพาะเมื่อมีสินค้าที่ "โผล่ในเรื่องอยู่แล้ว" หรือเกี่ยวโดยตรงจนคนดูอยากได้เอง
ถ้าต้องยัด/ฝืน = ห้ามแนบ (ปล่อยเป็นคลิปความรู้ล้วน สร้างฐานคนดู)

เรื่อง: {script}
หมวดสินค้าที่พอจะเกี่ยว (ถ้ามี): {hint}

ตอบเป็น JSON เท่านั้น:
{{"attach": true/false, "category": "หมวดสินค้า", "search": "คำค้นหาสินค้าบน Shopee",
  "soft_line": "ประโยคปิดเนียนๆ ที่โยงสินค้าเข้ากับเรื่อง (ถ้า attach=false ให้เป็นประโยคชวน follow/คอมเมนต์แทน ไม่มีลิงก์)"}}"""

MARKETING_PROMPT = """คุณคือนักการตลาดคอนเทนต์วิดีโอสั้นตลาดไทย จัดแพ็กเกจการโพสต์สำหรับสคริปต์นี้
สินค้า: {name} · สคริปต์: {script}

ต้องการ:
- youtube: title ≤ 60 ตัวอักษร — **เขียนเป็นประโยคบอกเล่า/หักล้างความเชื่อแบบฟันธง**
  (เช่น "เม่นไม่ได้สลัดขนใส่ศัตรู") ห้ามเป็นประโยคคำถาม ห้ามขึ้นต้นด้วย "ทำไม"
  ห้ามใช้คำขั้นสุด ("ที่สุดในโลก/อันดับ1") นำหน้า — ข้อมูลพิสูจน์แล้วว่า title แบบบอกเล่า
  ทำผลงานดีกว่าคำถาม/คำขั้นสุดมาก. ใส่ keyword ที่คนค้นจริงอย่างเนียน
  description 2-3 บรรทัด (keyword ธรรมชาติ + บรรทัดเปิดเผยผลประโยชน์: "{disclosure}")
- tiktok: caption สั้นชวนคุย จบด้วยคำถามชวนคอมเมนต์ + บรรทัดเปิดเผยผลประโยชน์
- extra_tags: แฮชแท็ก "เฉพาะคลิปนี้" 3 ตัว (เกาะหัวข้อ/หมวดสินค้า) — แท็กแบรนด์ตายตัวระบบเติมให้เอง

ตอบเป็น JSON เท่านั้น:
{{"youtube": {{"title": "...", "description": "..."}},
  "tiktok": {{"caption": "...", "extra_tags": ["#...", "#...", "#..."]}}}}"""


def _script_text(body: dict) -> str:
    return body["hook"] + " " + " ".join(body["lines"])


def generate_one(conn, product, cfg, suggested_angle: str | None = None) -> dict:
    sg = cfg.get("scriptgen", {})
    n_drafts = sg.get("drafts", 3)
    model = sg.get("model", cfg.get("model", "sonnet"))
    polish_model = sg.get("polish_model", model)

    # research brief upgrades raw material; seed facts remain the floor
    brief = research.ensure(conn, product, cfg)
    seed_facts = json.loads(product["facts"] or "[]")
    res_facts = [f["text"] for f in (brief or {}).get("facts", []) if f.get("text")]
    facts = "\n".join(f"- {f}" for f in seed_facts + res_facts)

    research_block = ""
    if brief:
        rs = brief.get("review_signals", {})
        research_block = (
            "\nวัตถุดิบเรื่องเล่าจากการรีเสิร์ช:\n"
            + "ความเข้าใจผิดยอดฮิต: "
            + " / ".join(brief.get("misconceptions", [])[:3])
            + "\nรีวิวมักชม: " + " / ".join(rs.get("praise", [])[:3])
            + "\nรีวิวมักบ่น: " + " / ".join(rs.get("complaints", [])[:3])
            + "\nบริบทไทย: " + str(brief.get("th_context", "")) + "\n")

    wmin, wmax = cfg["script_words"]
    common = dict(name=product["name"], category=product["category"] or "gadget",
                  price=int(product["price_thb"] or 0), facts=facts,
                  research_block=research_block,
                  cta=cfg["soft_cta"], wmin=wmin, wmax=wmax,
                  disclosure=cfg["disclosure"])

    # 1) drafts from distinct angles (director's suggestion always included)
    angles = random.sample(list(ANGLES), k=min(n_drafts, len(ANGLES)))
    if suggested_angle in ANGLES and suggested_angle not in angles:
        angles[0] = suggested_angle
    drafts = [claude_p(WRITE_PROMPT.format(angle_desc=ANGLES[a], **common), model)
              for a in angles]

    # 2) judge picks winner + weaknesses
    listing = "\n\n".join(
        f"ดราฟต์ {i} (angle: {a}):\n{json.dumps(d, ensure_ascii=False)}"
        for i, (a, d) in enumerate(zip(angles, drafts)))
    judge = claude_p(JUDGE_PROMPT.format(drafts=listing), model)
    best = int(judge.get("best", 0)) % len(drafts)

    # 3) polish rewrite on the strong model
    body = claude_p(POLISH_PROMPT.format(
        notes="\n".join(f"- {n}" for n in judge.get("notes", [])),
        body=json.dumps(drafts[best], ensure_ascii=False),
        wmin=wmin, wmax=wmax), polish_model)

    # 4) fact-check with one revise-and-recheck cycle
    def check(b: dict) -> dict:
        return claude_p(CHECK_PROMPT.format(
            name=product["name"], price=int(product["price_thb"] or 0),
            facts=facts, script=_script_text(b)), model)

    verdict = check(body)
    revised = False
    if verdict.get("verdict") != "pass":
        body = claude_p(REVISE_PROMPT.format(
            issues="\n".join(f"- {i}" for i in verdict.get("issues", [])),
            body=json.dumps(body, ensure_ascii=False)), model)
        verdict = check(body)
        revised = True

    # 5) marketing packaging (SEO title/description, platform captions/hashtags)
    try:
        body["marketing"] = claude_p(MARKETING_PROMPT.format(
            name=product["name"], script=_script_text(body),
            disclosure=cfg["disclosure"]), model)
    except Exception:
        pass  # publish stage falls back to the script caption

    # 6) shot plan — the editorial hand-off render/broll consume
    try:
        numbered = "\n".join(
            f"{i}. {t}" for i, t in enumerate([body["hook"], *body["lines"]]))
        subject = product["name"]
        body["shots"] = claude_p(SHOTS_PROMPT.format(
            numbered_lines=numbered, subject=subject), model).get("shots", [])
    except Exception:
        body["shots"] = []

    body["meta"] = {"angle": angles[best], "judge": judge, "revised": revised}
    status = "checked" if verdict.get("verdict") == "pass" else "rejected"
    conn.execute(
        "INSERT INTO scripts (product_id, hook_id, body, factcheck, status, created_at) "
        "VALUES (?,?,?,?,?,?)",
        (product["id"], angles[best], json.dumps(body, ensure_ascii=False),
         json.dumps(verdict, ensure_ascii=False), status, db.now()),
    )
    db.set_status(conn, "products", product["id"], "scripted")
    # research sources surface in the daily log so the operator can spot-check
    # the fact-checker's ground truth (it shares the research brief's trust)
    return {"product": product["name"], "angle": angles[best], "status": status,
            "revised": revised, "issues": verdict.get("issues", []),
            "sources": [f.get("source") for f in (brief or {}).get("facts", [])
                        if f.get("source")][:5]}


def generate_from_topic(conn, topic, cfg, suggested_angle: str | None = None) -> dict:
    """Story-first: research a topic → 3-draft/judge/opus-polish story → situational
    product attach → fact-check → marketing → shots. Product is optional."""
    sg = cfg.get("scriptgen", {})
    n_drafts = sg.get("drafts", 3)
    model = sg.get("model", cfg.get("model", "sonnet"))
    polish_model = sg.get("polish_model", model)

    brief = research.ensure_topic(conn, topic, cfg) or {}
    facts_list = [f["text"] for f in brief.get("facts", []) if f.get("text")]
    facts = "\n".join(f"- {f}" for f in facts_list) or f"- {topic['title']}"
    research_block = ""
    if brief:
        research_block = (
            "\nวัตถุดิบเรื่องเล่า:\nความเข้าใจผิด: "
            + " / ".join(brief.get("misconceptions", [])[:3])
            + "\nจุดหักมุม: " + str(brief.get("surprise", "")) + "\n")

    wmin, wmax = cfg["script_words"]
    common = dict(title=topic["title"], angle=topic["angle"] or "", facts=facts,
                  research_block=research_block, wmin=wmin, wmax=wmax)

    angles = random.sample(list(ANGLES), k=min(n_drafts, len(ANGLES)))
    if suggested_angle in ANGLES and suggested_angle not in angles:
        angles[0] = suggested_angle
    drafts = [claude_p(TOPIC_WRITE_PROMPT.format(angle_desc=ANGLES[a], **common), model)
              for a in angles]

    listing = "\n\n".join(
        f"ดราฟต์ {i} (angle: {a}):\n{json.dumps(d, ensure_ascii=False)}"
        for i, (a, d) in enumerate(zip(angles, drafts)))
    judge = claude_p(JUDGE_PROMPT.format(drafts=listing), model)
    best = int(judge.get("best", 0)) % len(drafts)

    body = claude_p(POLISH_PROMPT.format(
        notes="\n".join(f"- {n}" for n in judge.get("notes", [])),
        body=json.dumps(drafts[best], ensure_ascii=False),
        wmin=wmin, wmax=wmax), polish_model)

    # situational product attach — the story decides, never forced
    attach = {"attach": False}
    try:
        attach = claude_p(PRODUCT_MATCH_PROMPT.format(
            script=_script_text(body), hint=topic["product_hint"] or "-"), model)
    except Exception:
        pass
    if attach.get("attach"):
        # know the product before selling it — review-research + quality gate
        reviews = research.product_reviews(
            attach.get("search") or attach.get("category") or topic["title"], cfg)
        if reviews and reviews.get("worth_featuring") is False:
            attach = {"attach": False,
                      "soft_line": "กด follow ไว้ เดี๋ยวมีเรื่องน่ารู้มาเล่าอีก"}
            body["product"] = None
            if attach.get("soft_line"):
                body["lines"].append(attach["soft_line"])
        else:
            body["lines"].append(attach.get("soft_line", cfg["soft_cta"]))
            body["caption"] = (body.get("caption", "") + "\n" + cfg["disclosure"])
            body["product"] = {"category": attach.get("category"),
                               "search": attach.get("search"),
                               "reviews": reviews}
    else:
        if attach.get("soft_line"):
            body["lines"].append(attach["soft_line"])
        body["product"] = None

    # fact-check against researched facts (title stands in for product name)
    def check(b: dict) -> dict:
        return claude_p(CHECK_PROMPT.format(
            name=topic["title"], price=0, facts=facts,
            script=_script_text(b)), model)

    verdict = check(body)
    if verdict.get("verdict") != "pass":
        body = claude_p(REVISE_PROMPT.format(
            issues="\n".join(f"- {i}" for i in verdict.get("issues", [])),
            body=json.dumps(body, ensure_ascii=False)), model)
        verdict = check(body)

    try:
        body["marketing"] = claude_p(MARKETING_PROMPT.format(
            name=topic["title"], script=_script_text(body),
            disclosure=cfg["disclosure"]), model)
    except Exception:
        pass
    try:
        numbered = "\n".join(
            f"{i}. {t}" for i, t in enumerate([body["hook"], *body["lines"]]))
        subject = (body.get("product") or {}).get("category") or topic["title"]
        body["shots"] = claude_p(SHOTS_PROMPT.format(
            numbered_lines=numbered, subject=subject), model).get("shots", [])
    except Exception:
        body["shots"] = []

    body["meta"] = {"angle": angles[best], "topic_id": topic["id"],
                    "has_product": bool(body["product"]), "judge": judge}
    status = "checked" if verdict.get("verdict") == "pass" else "rejected"
    conn.execute(
        "INSERT INTO scripts (product_id, topic_id, hook_id, body, factcheck, status, created_at) "
        "VALUES (?,?,?,?,?,?,?)",
        (None, topic["id"], angles[best], json.dumps(body, ensure_ascii=False),
         json.dumps(verdict, ensure_ascii=False), status, db.now()))
    db.set_status(conn, "topics", topic["id"], "scripted")
    return {"topic": topic["title"], "angle": angles[best], "status": status,
            "has_product": bool(body["product"]),
            "product": body["product"], "sources": [f.get("source")
            for f in brief.get("facts", []) if f.get("source")][:5]}


def run(conn, cfg, limit: int = 1) -> list[dict]:
    results = []
    for product in db.rows(conn, "products", "discovered", limit,
                           order="score DESC, id"):
        try:
            results.append(generate_one(conn, product, cfg))
        except Exception as e:  # one bad product must not kill the run
            results.append({"product": product["name"], "status": "error", "error": str(e)})
    return results
