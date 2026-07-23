"""Stage 2 — script generation + fact-check via `claude -p` (headless).

Two passes per product:
  1. write: Thai short-video script from the hook bank (strict JSON out)
  2. check: verify every claim against the product's allowed facts; reject overreach
Costs nothing beyond the existing Claude subscription; model comes from config
(default sonnet to protect session limits).
"""
import json
import random
import subprocess
from pathlib import Path

from . import db

ROOT = Path(__file__).resolve().parent.parent

WRITE_PROMPT = """คุณเป็นคนเขียนสคริปต์วิดีโอสั้น (TikTok/Shorts) ภาษาไทย สายกล่อง-แกดเจ็ต
สไตล์: ให้ความรู้ ชวนสงสัย เล่าเรื่อง — ห้ามฟังดูเป็นโฆษณา ห้าม hard sell

สินค้า: {name} (หมวด {category}, ราคาประมาณ {price} บาท)
ข้อเท็จจริงที่ใช้ได้ (ห้ามอ้างเกินนี้):
{facts}

เปิดคลิปด้วยฮุคสไตล์: "{hook}"
โครง: ฮุค → ชวนสงสัย → ข้อเท็จจริงที่น่าสนใจ → เผยสินค้าแบบเนียนๆ → CTA เบาๆ ("{cta}")
ความยาวพูดรวม {wmin}-{wmax} คำ (20-40 วินาที)

ตอบเป็น JSON เท่านั้น ห้ามมีข้อความอื่น:
{{"hook": "...", "lines": ["ประโยคที่ 1", "ประโยคที่ 2", "..."],
  "caption": "แคปชันสั้น ลงท้ายด้วยบรรทัดเปิดเผยผลประโยชน์: {disclosure}",
  "hashtags": ["#...", "#...", "#..."]}}"""

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
- ภาษาพูด/การเล่าเกินจริงเชิงสำนวนที่ไม่ได้บิดเบือนข้อเท็จจริง

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


def claude_p(prompt: str, model: str) -> dict:
    out = subprocess.run(
        ["claude", "-p", prompt, "--model", model],
        capture_output=True, text=True, timeout=300,
    )
    if out.returncode != 0:
        raise RuntimeError(f"claude -p failed: {out.stderr[:500]}")
    text = out.stdout
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end == -1:
        raise ValueError(f"no JSON in claude output: {text[:200]}")
    return json.loads(text[start:end + 1])


def generate_one(conn, product, cfg) -> dict:
    hook = random.choice(cfg["hooks"])
    facts = "\n".join(f"- {f}" for f in json.loads(product["facts"] or "[]"))
    wmin, wmax = cfg["script_words"]

    def check(body: dict) -> dict:
        script_text = body["hook"] + " " + " ".join(body["lines"])
        return claude_p(CHECK_PROMPT.format(
            name=product["name"], price=int(product["price_thb"] or 0),
            facts=facts, script=script_text), cfg["model"])

    body = claude_p(WRITE_PROMPT.format(
        name=product["name"], category=product["category"] or "gadget",
        price=int(product["price_thb"] or 0), facts=facts, hook=hook["th"],
        cta=cfg["soft_cta"], wmin=wmin, wmax=wmax, disclosure=cfg["disclosure"],
    ), cfg["model"])

    verdict = check(body)
    revised = False
    if verdict.get("verdict") != "pass":  # one revise-and-recheck cycle
        body = claude_p(REVISE_PROMPT.format(
            issues="\n".join(f"- {i}" for i in verdict.get("issues", [])),
            body=json.dumps(body, ensure_ascii=False)), cfg["model"])
        verdict = check(body)
        revised = True

    status = "checked" if verdict.get("verdict") == "pass" else "rejected"
    conn.execute(
        "INSERT INTO scripts (product_id, hook_id, body, factcheck, status, created_at) "
        "VALUES (?,?,?,?,?,?)",
        (product["id"], hook["id"], json.dumps(body, ensure_ascii=False),
         json.dumps(verdict, ensure_ascii=False), status, db.now()),
    )
    db.set_status(conn, "products", product["id"], "scripted")
    return {"product": product["name"], "hook": hook["id"], "status": status,
            "revised": revised, "issues": verdict.get("issues", [])}


def run(conn, cfg, limit: int = 1) -> list[dict]:
    results = []
    for product in db.rows(conn, "products", "discovered", limit):
        try:
            results.append(generate_one(conn, product, cfg))
        except Exception as e:  # one bad product must not kill the run
            results.append({"product": product["name"], "status": "error", "error": str(e)})
    return results
