"""Affiliate-availability gate — the product a story attaches must have a REAL,
attachable affiliate link (Shopee/Lazada/TikTok Shop). Premium brands (Apple, etc.)
have no TH affiliate program, so a story that resolves to "Apple Watch" is unshippable.

Rule (from the TH affiliate research): attach only GENERIC, affiliate-able product
categories in the impulse price band; hard-block premium brands as the terminal product.
The product is locked BEFORE the script commits, so the narration talks about the
generic product's use-case, never a premium brand (no bait-and-switch).
"""

# Premium / no-TH-affiliate brands — never the terminal product, whatever footage inspired it.
BRAND_DENYLIST = (
    "apple", "iphone", "ipad", "macbook", "airpod", "apple watch",
    "samsung galaxy", "galaxy s2", "galaxy s10", "galaxy s20", "galaxy s21",
    "galaxy s22", "galaxy s23", "galaxy s24", "galaxy note", "galaxy fold",
    "galaxy z", "galaxy watch", "dyson", "bose", "sony wh", "sony wf", "dji",
    "gopro", "garmin", "fitbit", "nintendo", "playstation", "ps5", "xbox",
    "nikon", "canon", "sonos", "marshall", "bang & olufsen", "tesla", "insta360",
)

# Impulse band that converts + is worth a seller's affiliate top-up (THB).
PRICE_MIN, PRICE_MAX = 100, 900

# Generic, reliably affiliate-able TH gadget categories (guidance for the matcher).
ALLOW_CATEGORIES = (
    "สมาร์ทวอทช์ราคาประหยัด", "สายรัดข้อมือสุขภาพ/fitness ring", "พาวเวอร์แบงก์",
    "สายชาร์จ/หัวชาร์จ", "หูฟังบลูทูธราคาประหยัด", "เคส/ฟิล์มมือถือ", "พัดลมพกพา",
    "เครื่องปั่นพกพา", "ไฟ LED/ไฟตกแต่ง", "อุปกรณ์จัดระเบียบ", "แกดเจ็ตในบ้าน/รถ",
    "ที่วางมือถือ/ขาตั้ง", "อุปกรณ์ทำความสะอาด", "ของใช้ตามฤดูกาล",
)


def _denied_brand(text: str) -> str | None:
    t = (text or "").lower()
    return next((b for b in BRAND_DENYLIST if b in t), None)


def gate(attach: dict) -> dict:
    """Enforce affiliate-availability on a product-match result. Returns the attach dict,
    downgraded to attach=False (with a follow CTA) if the product isn't affiliate-able."""
    if not isinstance(attach, dict) or not attach.get("attach"):
        return attach if isinstance(attach, dict) else {"attach": False}

    blob = f"{attach.get('category', '')} {attach.get('search', '')} {attach.get('name', '')}"
    brand = _denied_brand(blob)
    if brand:
        return {"attach": False, "affiliate_reject": f"premium brand '{brand}' (no TH affiliate)",
                "soft_line": attach.get("soft_line_generic")
                or "กด follow ไว้ เดี๋ยวมีของน่าใช้ราคาน่ารักมาเล่าให้อีก"}

    price = attach.get("price_thb")
    try:
        if price is not None and not (PRICE_MIN <= float(price) <= PRICE_MAX):
            return {"attach": False, "affiliate_reject": f"price {price} outside ฿{PRICE_MIN}-{PRICE_MAX}",
                    "soft_line": "กด follow ไว้ เดี๋ยวมีของน่าใช้ราคาน่ารักมาเล่าให้อีก"}
    except (TypeError, ValueError):
        pass
    return attach
