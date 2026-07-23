"""Stage 3.5 — footage finding. Resolve each shot's search query to the best
available licensed clip, across sources, with a quality gate and query broadening.

Source chain (best → fallback), all commercial-use-safe:
  1. product media   — the product's own listing video (highest relevance, when given)
  2. Pexels          — keyed, curated, portrait-native (best when PEXELS_API_KEY set)
  3. Pixabay         — keyed fallback
  4. Wikimedia       — KEYLESS: works with zero API keys (CC/PD; grab-bag quality)
  5. gradient        — render.py fallback when nothing resolves

Each candidate is scored on resolution, orientation, and duration; sub-HD junk is
rejected. If a specific query finds nothing, it is broadened before giving up.
"""
import hashlib
import os
import time
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
CACHE = ROOT / "assets" / "cache" / "broll"
# Wikimedia policy requires a descriptive UA with contact — reduces 429s
UA = "shorts-factory/1.0 (https://github.com/Puen2001/AF) requests"


def _get(url, **kw):
    """GET with polite backoff on Wikimedia 429 rate-limiting."""
    kw.setdefault("headers", {}).setdefault("User-Agent", UA)
    for attempt in range(3):
        r = requests.get(url, **kw)
        if r.status_code == 429:
            time.sleep(2 * (attempt + 1))
            continue
        return r
    return r

MIN_H = 640          # reject clips shorter than this — no 480p mush
DUR_MIN, DUR_MAX = 3, 40


def _score(c: dict) -> float:
    """Rank candidates: resolution + portrait bonus + sane duration."""
    h, w, d = c["height"], c["width"], c.get("duration") or 8
    s = min(h, 2160) / 120.0
    if h < MIN_H:
        s -= 100                       # effectively disqualify
    s += 18 if h >= w else 0           # portrait needs no crop → prefer it
    s += 12 if h >= 1080 else 0        # HD bonus
    s += 8 if DUR_MIN <= d <= DUR_MAX else -8
    return s


def _pexels(query: str) -> list[dict]:
    key = os.environ.get("PEXELS_API_KEY")
    if not key:
        return []
    try:
        r = requests.get("https://api.pexels.com/videos/search",
                         headers={"Authorization": key},
                         params={"query": query, "orientation": "portrait",
                                 "per_page": 8}, timeout=30)
        r.raise_for_status()
        out = []
        for v in r.json().get("videos", []):
            files = [f for f in v.get("video_files", []) if f.get("height")]
            best = max(files, key=lambda f: f["height"], default=None)
            if best:
                out.append({"url": best["link"], "width": best.get("width", 0),
                            "height": best["height"], "duration": v.get("duration"),
                            "source": "pexels"})
        return out
    except Exception:
        return []


def _pixabay(query: str) -> list[dict]:
    key = os.environ.get("PIXABAY_API_KEY")
    if not key:
        return []
    try:
        r = requests.get("https://pixabay.com/api/videos/",
                         params={"key": key, "q": query, "per_page": 8}, timeout=30)
        r.raise_for_status()
        out = []
        for v in r.json().get("hits", []):
            f = v.get("videos", {}).get("large") or v.get("videos", {}).get("medium")
            if f and f.get("url"):
                out.append({"url": f["url"], "width": f.get("width", 0),
                            "height": f.get("height", 0), "duration": v.get("duration"),
                            "source": "pixabay"})
        return out
    except Exception:
        return []


def _wikimedia(query: str) -> list[dict]:
    """Keyless CC/PD video from Wikimedia Commons. Works with no API keys at all."""
    api = "https://commons.wikimedia.org/w/api.php"
    try:
        s = _get(api, params={
            "action": "query", "format": "json", "list": "search",
            "srsearch": f"filetype:video {query}", "srnamespace": 6, "srlimit": 8},
            timeout=20)
        s.raise_for_status()
        titles = [r["title"] for r in s.json().get("query", {}).get("search", [])]
        if not titles:
            return []
        info = _get(api, params={
            "action": "query", "format": "json", "prop": "imageinfo",
            "iiprop": "url|size", "titles": "|".join(titles[:8])},
            timeout=20)
        info.raise_for_status()
        out = []
        for p in info.json().get("query", {}).get("pages", {}).values():
            ii = (p.get("imageinfo") or [{}])[0]
            title = p.get("title", "").lower()
            # skip anything that reads as a disaster/graphic clip (safety)
            if any(w in title for w in ("crash", "wreck", "fire", "accident",
                                        "explosion", "war", "death")):
                continue
            if ii.get("url") and ii.get("height"):
                out.append({"url": ii["url"], "width": ii.get("width", 0),
                            "height": ii["height"], "duration": ii.get("duration"),
                            "source": "wikimedia"})
        return out
    except Exception:
        return []


def _archive_org(query: str) -> list[dict]:
    """Keyless public-domain VIDEO from Archive.org. Legal, no API key. Coverage is
    thin for gadgets (skews documentary/archival) but it's real, free, licensed video."""
    try:
        r = _get("https://archive.org/advancedsearch.php", params={
            "q": f'({query}) AND mediatype:movies AND format:(MP4)',
            "fl[]": "identifier", "rows": 4, "output": "json"}, timeout=20)
        r.raise_for_status()
        out = []
        for doc in r.json().get("response", {}).get("docs", []):
            ident = doc.get("identifier")
            if not ident:
                continue
            m = _get(f"https://archive.org/metadata/{ident}", timeout=20)
            files = m.json().get("files", [])
            mp4 = next((f for f in files
                        if f.get("name", "").lower().endswith(".mp4")
                        and int(f.get("height", 0) or 0) >= MIN_H), None)
            if mp4:
                out.append({"url": f"https://archive.org/download/{ident}/{mp4['name']}",
                            "width": int(mp4.get("width", 0) or 0),
                            "height": int(mp4.get("height", 0) or 0),
                            "duration": None, "source": "archive.org"})
        return out
    except Exception:
        return []


def _wikimedia_image(query: str) -> list[dict]:
    """Keyless still images from Commons (product photos etc.). Rendered with Ken
    Burns motion. Abundant + lighter than video, so a good product-shot source."""
    api = "https://commons.wikimedia.org/w/api.php"
    try:
        r = _get(api, params={
            "action": "query", "format": "json", "generator": "search",
            "gsrsearch": query, "gsrnamespace": 6, "gsrlimit": 10,
            "prop": "imageinfo", "iiprop": "url|size|mediatype"}, timeout=20)
        r.raise_for_status()
        out = []
        for p in r.json().get("query", {}).get("pages", {}).values():
            ii = (p.get("imageinfo") or [{}])[0]
            title = p.get("title", "").lower()
            if ii.get("mediatype") != "BITMAP" or ii.get("width", 0) < 800:
                continue
            if any(w in title for w in ("crash", "wreck", "accident", "death")):
                continue
            out.append({"url": ii["url"], "width": ii.get("width", 0),
                        "height": ii.get("height", 0), "duration": None,
                        "kind": "image", "source": "wikimedia-img"})
        return out
    except Exception:
        return []


def _broaden(query: str):
    """Yield the query, then progressively broader versions (drop trailing words)."""
    words = (query or "").split()
    yield query
    if len(words) >= 3:
        yield " ".join(words[:2])
    if len(words) >= 2:
        yield words[0]


def _best_for(query: str, want_product: bool = False) -> dict | None:
    """Find the best clip/still for a query. Keyless image catalogs are far richer
    than keyless video, so a MATCHING still (Ken-Burns'd) beats a mismatched clip —
    images are always in the candidate pool, not just a last resort."""
    for q in _broaden(query):
        if not q:
            continue
        cands = _pexels(q) + _pixabay(q) + _wikimedia(q) + _wikimedia_image(q)
        cands = [c for c in cands if c["height"] >= MIN_H
                 and (c.get("duration") is None or c["duration"] >= DUR_MIN)]
        if cands:
            return max(cands, key=_score)
    return None


def _download(url: str) -> str | None:
    CACHE.mkdir(parents=True, exist_ok=True)
    ext = ".mp4" if ".mp4" in url.lower() else (".webm" if "webm" in url.lower() else ".mp4")
    path = CACHE / (hashlib.sha1(url.encode()).hexdigest()[:14] + ext)
    if path.exists():
        return str(path)
    try:
        with _get(url, stream=True, timeout=180) as r:
            r.raise_for_status()
            written = 0
            with open(path, "wb") as f:
                for chunk in r.iter_content(1 << 16):
                    written += len(chunk)
                    if written > 200 * 1024 * 1024:
                        raise ValueError("clip exceeds 200MB cap")
                    f.write(chunk)
        return str(path)
    except Exception:
        path.unlink(missing_ok=True)
        return None


def resolve(shots: list[dict], cfg: dict | None = None,
            product_media: list[str] | None = None) -> list[dict]:
    """Attach a local clip file to each shot (file=None if unresolvable → gradient).
    product_media (direct clip URLs from the product listing) is tried first."""
    media_pool = list(product_media or [])
    out = []
    is_img = lambda f: f and str(f).lower().rsplit(".", 1)[-1] in (
        "jpg", "jpeg", "png", "webp")
    for i, s in enumerate(shots or []):
        if s.get("file"):
            out.append(s)
            continue
        chosen, is_product = None, s.get("type") == "product"
        # product's own listing photo first — most relevant + license-clean
        if i < len(media_pool):
            chosen = _download(media_pool[i])
        if not chosen:
            best = _best_for((s.get("query") or "").strip(), want_product=is_product)
            if best:
                chosen = _download(best["url"])
                if chosen:
                    s = {**s, "source": best["source"], "res": best["height"]}
        # transform a raw product still into a clean branded shot (safer + nicer)
        if chosen and is_product and is_img(chosen):
            from . import product_shot
            shot = product_shot.make(chosen, idx=i)
            if shot:
                chosen = shot
                s = {**s, "composited": True}
        out.append({**s, "file": chosen})
    return out
