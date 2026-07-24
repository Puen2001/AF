"""Stage 3.4 — VIDEO footage discovery (the reference-tier engine).

Video-only, keyless: searches YouTube for real footage matching each shot's visual
intent and downloads a SHORT SEGMENT (not the whole video) as a real .mp4 clip.
This is the source that actually shows the product / the scene — stock libraries
have no clip of a specific gadget, so they fall back to gradients.

Design (docs/FOOTAGE-DISCOVERY-ENGINE.md): YouTube is the reference tier — the human
reviews and keeps/licenses via the curate page. The auto path may use a segment
directly (operator's channel, operator's call). NO still images — video only.

Cheap by construction: `download_ranges` fetches only a few seconds per candidate,
so a 6-minute review costs ~3-4MB and ~10s, and everything is cached by (id, window).
"""
import hashlib
import os
import subprocess
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CACHE = ROOT / "assets" / "cache" / "footage"

# reuse broll's brand-safety title gate so we never pull suggestive/graphic footage
from .broll import _safe

# yt-dlp search filters out these noise words that hurt YouTube relevance
_STOP = {"closeup", "close-up", "macro", "shot", "footage", "clip", "scene",
         "background", "then", "and", "the", "a", "of", "in", "on", "inside",
         "into", "with", "next", "size", "comparison", "digital", "display"}


def _yt_query(query: str, max_words: int = 6) -> str:
    """YouTube search likes short noun-heavy queries, not full visual sentences.
    Drop filler words, keep the first few meaningful ones."""
    words = [w for w in (query or "").split() if w.lower() not in _STOP]
    return " ".join(words[:max_words]) or (query or "").strip()


def _search(query: str, n: int = 6) -> list[dict]:
    """Search YouTube (keyless) → candidate videos, brand-safe, sane length."""
    try:
        import yt_dlp
    except Exception:
        return []
    q = _yt_query(query)
    if not q:
        return []
    opts = {"quiet": True, "no_warnings": True, "skip_download": True,
            "extract_flat": "in_playlist", "noplaylist": True,
            "default_search": "ytsearch", "socket_timeout": 20}
    out = []
    try:
        with yt_dlp.YoutubeDL(opts) as y:
            info = y.extract_info(f"ytsearch{n*2}:{q}", download=False)
    except Exception:
        return []
    for e in (info.get("entries") or []):
        if not e:
            continue
        title = e.get("title") or ""
        dur = e.get("duration")
        if not _safe(title):
            continue
        # skip livestreams / unknown-length / very long (>25min) uploads
        if dur is None or dur < 8 or dur > 1500:
            continue
        out.append({"id": e.get("id"), "title": title, "duration": dur,
                    "url": f"https://www.youtube.com/watch?v={e.get('id')}"})
        if len(out) >= n:
            break
    return out


def _window(dur: float, want: float) -> tuple[float, float]:
    """Pick a segment past the talking-head intro. Reviews open with a face; the
    product B-roll is deeper in. Start ~18% in, clamped to leave room for `want`."""
    want = max(3.0, min(want, 12.0))
    start = max(6.0, dur * 0.18)
    start = min(start, max(0.0, dur - want - 1.0))
    return round(start, 1), round(start + want, 1)


def _download_segment(video_id: str, start: float, end: float) -> str | None:
    """Download ONLY [start,end] of a YouTube video as a real .mp4. Cached."""
    try:
        import yt_dlp
    except Exception:
        return None
    CACHE.mkdir(parents=True, exist_ok=True)
    key = hashlib.sha1(f"{video_id}:{start}:{end}".encode()).hexdigest()[:14]
    path = CACHE / f"{key}.mp4"
    if path.exists() and path.stat().st_size > 20_000:
        return str(path)
    opts = {
        "quiet": True, "no_warnings": True,
        "format": "bestvideo[height<=1280][ext=mp4]+bestaudio/best[height<=1280]",
        "outtmpl": str(CACHE / f"{key}.%(ext)s"),
        "download_ranges": lambda info, ydl: [{"start_time": start, "end_time": end}],
        "force_keyframes_at_cuts": True,
        "merge_output_format": "mp4",
        "socket_timeout": 30,
        "retries": 2,
    }
    try:
        with yt_dlp.YoutubeDL(opts) as y:
            y.download([f"https://www.youtube.com/watch?v={video_id}"])
    except Exception:
        for f in CACHE.glob(f"{key}.*"):
            f.unlink(missing_ok=True)
        return None
    if not path.exists():                       # merged to a different container?
        alt = next((p for p in CACHE.glob(f"{key}.*")), None)
        if alt:
            try:
                alt.rename(path)
            except Exception:
                return str(alt)
    if path.exists() and _is_playable_video(path):
        return str(path)
    path.unlink(missing_ok=True)
    return None


def _is_playable_video(path: Path) -> bool:
    """ffprobe check: a real video stream with non-zero duration."""
    try:
        r = subprocess.run(
            ["ffprobe", "-v", "error", "-select_streams", "v:0",
             "-show_entries", "stream=codec_name,duration", "-of", "csv=p=0",
             str(path)], capture_output=True, text=True, timeout=20)
        return r.returncode == 0 and "," in r.stdout
    except Exception:
        return False


def best_clip(query: str, want_seconds: float = 6.0) -> dict | None:
    """AUTO path: the single best real video segment for a shot query (or None)."""
    for cand in _search(query, n=5):
        start, end = _window(cand["duration"], want_seconds)
        f = _download_segment(cand["id"], start, end)
        if f:
            return {"file": f, "source": "youtube", "url": cand["url"],
                    "title": cand["title"], "start": start, "end": end}
    return None


def shortlist(query: str, want_seconds: float = 6.0, n: int = 4) -> list[dict]:
    """CURATE path: up to n real video segments for a shot, for the human to pick.
    Returns rich references (url/title/why) with the downloaded local file."""
    out = []
    for cand in _search(query, n=n + 3):
        start, end = _window(cand["duration"], want_seconds)
        f = _download_segment(cand["id"], start, end)
        if not f:
            continue
        out.append({"file": f, "source": "youtube", "url": cand["url"],
                    "title": cand["title"], "start": start, "end": end,
                    "why": f"YouTube match for “{_yt_query(query)}”"})
        if len(out) >= n:
            break
    return out
