"""Stage 3.5 — b-roll research: resolve the script's shot plan to licensed clips.

Pexels (primary) and Pixabay (fallback) free APIs; both licenses permit
commercial use without attribution. No key / no result → the shot stays
unresolved and the renderer falls back to a gradient scene for that segment.
Clips cache by query so repeat topics cost zero calls.
"""
import hashlib
import os
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
CACHE = ROOT / "assets" / "cache" / "broll"


def _pexels(query: str) -> str | None:
    key = os.environ.get("PEXELS_API_KEY")
    if not key:
        return None
    r = requests.get("https://api.pexels.com/videos/search",
                     headers={"Authorization": key},
                     params={"query": query, "orientation": "portrait",
                             "size": "medium", "per_page": 6},
                     timeout=30)
    r.raise_for_status()
    for v in r.json().get("videos", []):
        if v.get("duration", 0) < 4:
            continue
        files = sorted((f for f in v.get("video_files", [])
                        if f.get("height", 0) >= 1280
                        and f.get("width", 0) <= f.get("height", 0)),
                       key=lambda f: f["height"])
        if files:
            return files[0]["link"]
    return None


def _pixabay(query: str) -> str | None:
    key = os.environ.get("PIXABAY_API_KEY")
    if not key:
        return None
    r = requests.get("https://pixabay.com/api/videos/",
                     params={"key": key, "q": query, "per_page": 6},
                     timeout=30)
    r.raise_for_status()
    for v in r.json().get("hits", []):
        if v.get("duration", 0) < 4:
            continue
        best = v.get("videos", {}).get("large") or v.get("videos", {}).get("medium")
        if best and best.get("url"):
            return best["url"]
    return None


def resolve(shots: list[dict]) -> list[dict]:
    """Attach a local clip file to each shot (or file=None if unresolvable)."""
    CACHE.mkdir(parents=True, exist_ok=True)
    out = []
    for s in shots or []:
        q = (s.get("query") or "").strip()
        if not q:
            out.append({**s, "file": None})
            continue
        path = CACHE / (hashlib.sha1(q.encode()).hexdigest()[:12] + ".mp4")
        if path.exists():
            out.append({**s, "file": str(path)})
            continue
        url = None
        try:
            url = _pexels(q) or _pixabay(q)
            if url:
                with requests.get(url, stream=True, timeout=120) as r:
                    r.raise_for_status()
                    with open(path, "wb") as f:
                        for chunk in r.iter_content(1 << 16):
                            f.write(chunk)
        except Exception:
            path.unlink(missing_ok=True)
            url = None
        out.append({**s, "file": str(path) if url else None})
    return out
