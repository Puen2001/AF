"""Turn a raw product/listing photo into a clean, branded product SHOT.

Removes the background (rembg / BiRefNet) and composites the cutout onto a
gradient backdrop with a soft drop shadow — a still image the renderer then
Ken-Burns's. This is BOTH better-looking than a raw listing screenshot AND
legally safer (a transformed work, not a copy). Free, self-hosted, CPU-fine.

Product is placed upper-center so bottom captions never cover it (9:16 rule).
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CACHE = ROOT / "assets" / "cache" / "product"

W, H = 1080, 1920
# dark backdrop palettes (top, bottom) matching the render gradient family
BACKDROPS = [
    ((16, 18, 34), (44, 26, 62)),
    ((13, 27, 42), (27, 58, 75)),
    ((26, 18, 6), (58, 42, 18)),
    ((20, 20, 20), (46, 38, 32)),
]

_session = None


def _remove_bg(img):
    """rembg cutout (RGBA). Lazy-load the session so import stays cheap."""
    global _session
    from rembg import remove, new_session
    if _session is None:
        _session = new_session("isnet-general-use")   # strong general matte
    return remove(img, session=_session, post_process_mask=True)


def _gradient(top, bottom):
    from PIL import Image
    base = Image.new("RGB", (1, H))
    px = base.load()
    for y in range(H):
        t = y / (H - 1)
        px[0, y] = tuple(int(top[c] + (bottom[c] - top[c]) * t) for c in range(3))
    return base.resize((W, H))


def _glow(cx, cy, radius):
    """Soft radial glow behind the product for depth."""
    from PIL import Image, ImageDraw, ImageFilter
    layer = Image.new("L", (W, H), 0)
    d = ImageDraw.Draw(layer)
    d.ellipse([cx - radius, cy - radius, cx + radius, cy + radius], fill=90)
    return layer.filter(ImageFilter.GaussianBlur(radius // 2))


def make(src_image: str, out_path: str | None = None, idx: int = 0) -> str | None:
    """Composite src product photo → branded product shot at out_path (PNG)."""
    try:
        from PIL import Image, ImageFilter
    except ImportError:
        return None
    src = Path(src_image)
    if not src.exists():
        return None
    CACHE.mkdir(parents=True, exist_ok=True)
    out = Path(out_path) if out_path else CACHE / (src.stem + "_shot.png")

    try:
        img = Image.open(src).convert("RGBA")
        cut = _remove_bg(img)
        bbox = cut.getbbox()
        if not bbox:                       # nothing found — bail to raw
            return None
        cut = cut.crop(bbox)

        # scale product to ~58% of canvas height, cap width at 82%
        target_h = int(H * 0.58)
        scale = target_h / cut.height
        if cut.width * scale > W * 0.82:
            scale = (W * 0.82) / cut.width
        cut = cut.resize((max(1, int(cut.width * scale)),
                          max(1, int(cut.height * scale))), Image.LANCZOS)

        # upper-center placement (leaves the lower third for captions)
        px = (W - cut.width) // 2
        py = int(H * 0.30) - cut.height // 2
        cx, cy = px + cut.width // 2, py + cut.height // 2

        top, bottom = BACKDROPS[idx % len(BACKDROPS)]
        canvas = _gradient(top, bottom).convert("RGBA")
        # glow
        glow = _glow(cx, cy, int(cut.width * 0.75))
        glow_rgba = Image.new("RGBA", (W, H), (255, 255, 255, 0))
        glow_rgba.putalpha(glow)
        canvas = Image.alpha_composite(canvas, glow_rgba)
        # soft drop shadow (offset, blurred silhouette)
        shadow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        sil = Image.new("RGBA", cut.size, (0, 0, 0, 160))
        sil.putalpha(cut.split()[3].point(lambda a: int(a * 0.55)))
        shadow.paste(sil, (px + 14, py + 26), sil)
        shadow = shadow.filter(ImageFilter.GaussianBlur(22))
        canvas = Image.alpha_composite(canvas, shadow)
        # product
        canvas.alpha_composite(cut, (px, py))

        canvas.convert("RGB").save(out, "PNG")
        return str(out)
    except Exception:
        return None
