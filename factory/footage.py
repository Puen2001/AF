"""Stage 3.4 — VIDEO footage discovery (the reference-tier engine, vision-guided).

Video-only, keyless, use-case-first. For each shot it does NOT just grab a segment —
it *looks* at candidate footage and picks the moment that actually shows the scene:

  1. search YouTube + TikTok with USE-CASE-biased, product-anchored queries
  2. download a cheap low-res PROXY of each candidate
  3. build a timestamped contact sheet (a grid of frames) and let Claude SEE it —
     "which moment shows <product> actually being used?" (rejects wrong-product /
     talking-head / no-use-case footage — the two failures of the naive version)
  4. quality-extract a short clip around the chosen timestamp

Copyright: the operator's channel uses found footage freely (operator's call), so the
auto path downloads and uses directly. NO still images — video only.

Cost control: the proxy is 360p and the vision judgement is ONE call per candidate
video (a single contact sheet, not per-frame). Everything is cached.
"""
import hashlib
import json
import subprocess
from pathlib import Path

from .broll import _safe
from .llm import claude_p

ROOT = Path(__file__).resolve().parent.parent
CACHE = ROOT / "assets" / "cache" / "footage"
PROXY = CACHE / "proxy"
SHEET = CACHE / "sheet"
VISION_MODEL = "sonnet"          # cheap vision judge; override via cfg if needed

_STOP = {"closeup", "close-up", "macro", "shot", "footage", "clip", "scene",
         "background", "then", "and", "the", "a", "of", "in", "on", "inside",
         "into", "with", "next", "size", "comparison", "digital", "display",
         "glowing", "warm"}


def _core_terms(query: str, max_words: int = 5) -> str:
    words = [w for w in (query or "").split() if w.lower() not in _STOP]
    return " ".join(words[:max_words]) or (query or "").strip()


def _queries(query: str, product_name: str | None) -> list[str]:
    """Use-case-biased search queries. Product shots get the product name anchored
    to demonstration terms so we land on real usage, not unboxings or talking heads."""
    core = _core_terms(query)
    if product_name:
        p = product_name.strip()
        return [f"{p} รีวิว การใช้งาน", f"{p} วิธีใช้", f"{p} demo review", p]
    # b-roll / metaphor shots: the literal visual, plus a tightened core
    return [query.strip(), core] if core != query.strip() else [query.strip()]


def _search(queries: list[str], n: int = 4) -> list[dict]:
    """YouTube + TikTok candidates, brand-safe, sane length, de-duped by id."""
    try:
        import yt_dlp
    except Exception:
        return []
    opts = {"quiet": True, "no_warnings": True, "skip_download": True,
            "extract_flat": "in_playlist", "noplaylist": True, "socket_timeout": 20}
    seen, out = set(), []
    for q in queries:
        if not q or len(out) >= n:
            continue
        for prefix, plat in ((f"ytsearch{n}:", "youtube"),):
            try:
                with yt_dlp.YoutubeDL(opts) as y:
                    info = y.extract_info(prefix + q, download=False)
            except Exception:
                continue
            for e in (info.get("entries") or []):
                if not e or e.get("id") in seen:
                    continue
                title, dur = e.get("title") or "", e.get("duration")
                if not _safe(title) or dur is None or dur < 8 or dur > 900:
                    continue
                seen.add(e.get("id"))
                out.append({"id": e.get("id"), "title": title, "duration": dur,
                            "platform": plat,
                            "url": f"https://www.youtube.com/watch?v={e.get('id')}"})
                if len(out) >= n:
                    break
    return out


def _proxy_download(video_id: str) -> str | None:
    """Cheap 360p proxy of the whole (short) video — for frame sampling only."""
    try:
        import yt_dlp
    except Exception:
        return None
    PROXY.mkdir(parents=True, exist_ok=True)
    path = PROXY / f"{video_id}.mp4"
    if path.exists() and path.stat().st_size > 20_000:
        return str(path)
    opts = {"quiet": True, "no_warnings": True,
            "format": "best[height<=360][ext=mp4]/worst[ext=mp4]/worst",
            "outtmpl": str(PROXY / f"{video_id}.%(ext)s"),
            "socket_timeout": 30, "retries": 2, "noprogress": True}
    try:
        with yt_dlp.YoutubeDL(opts) as y:
            y.download([f"https://www.youtube.com/watch?v={video_id}"])
    except Exception:
        for f in PROXY.glob(f"{video_id}.*"):
            f.unlink(missing_ok=True)
        return None
    if not path.exists():
        alt = next((p for p in PROXY.glob(f"{video_id}.*")), None)
        return str(alt) if alt else None
    return str(path)


def _contact_sheet(video_path: str, video_id: str, dur: float) -> str | None:
    """A 3x4 grid of 12 evenly-spaced frames, each burned with its source timestamp,
    so the vision judge can name the moment (mm:ss) that shows the use-case."""
    SHEET.mkdir(parents=True, exist_ok=True)
    out = SHEET / f"{video_id}.jpg"
    if out.exists():
        return str(out)
    n = 12
    fps = max(n / max(dur, 1.0), 0.05)     # ~12 frames across the whole clip
    vf = (f"fps={fps:.4f},scale=360:-1,"
          f"drawtext=text='%{{pts\\:hms}}':x=6:y=6:fontsize=22:fontcolor=yellow:"
          f"box=1:boxcolor=black@0.6,tile=3x4")
    try:
        r = subprocess.run(
            ["ffmpeg", "-y", "-i", video_path, "-vf", vf, "-frames:v", "1",
             str(out)], capture_output=True, text=True, timeout=120)
        if r.returncode == 0 and out.exists():
            return str(out)
    except Exception:
        pass
    return None


def _vision_pick(sheet_path: str, requirement: str,
                 product_name: str | None) -> dict | None:
    """Claude LOOKS at the contact sheet and returns the best moment. This is the
    step that enforces 'shows the product being used' + 'matches this shot'."""
    prod = (f"\n  This beat SHOWS THE PRODUCT — the exact product must be visible: "
            f"{product_name}. A different product (e.g. a 3D printer when we need a label "
            f"printer; a tower fan when we need a handheld fan) is WRONG_PRODUCT."
            if product_name else "")
    prompt = (
        f"Use the Read tool to open the image at {sheet_path}. It is a 3x4 grid of "
        f"12 video frames; each frame has its source timestamp (mm:ss) burned in the "
        f"top-left in yellow.\n\n"
        f"This is compilation B-ROLL for a curiosity short-form video (TOGE-style). I need "
        f"ONE frame for this narration beat:\n"
        f"  BEAT: {requirement}{prod}\n\n"
        f"THE MUTED TEST — the main rule: with the sound OFF, does the frame visually "
        f"communicate THIS beat's meaning? Pick the frame that best illustrates THIS "
        f"exact sentence.\n"
        f"- Faces are OK when the beat is a human reaction/use (reacting, tasting, holding, "
        f"demonstrating). Do NOT reject just for a face.\n"
        f"- BUT AVOID (pick a cleaner frame if one exists): (a) frames with large BURNED-IN "
        f"text/subtitles/captions on them — they clash with our own captions; (b) for a "
        f"PRODUCT beat, a person just TALKING TO CAMERA (a reviewer) when the product itself "
        f"is barely shown — prefer the product actually in use.\n"
        f"- Any authentic footage type qualifies: reaction, hands demonstrating, object "
        f"close-up, comparison, product-in-use, real-world scene.\n"
        f"- REJECT a frame only if it does NOT illustrate this beat (unrelated / generic "
        f"filler){' or shows a WRONG product' if product_name else ''}.\n\n"
        f"Pick the single best frame and read its burned-in timestamp. Reply ONLY JSON:\n"
        f"{{\"ts\":\"mm:ss\", \"seconds\":<int>, \"illustrates\":true|false, "
        f"\"wrong_product\":true|false, \"heavy_text\":true|false, \"match\":0-1, "
        f"\"seen\":\"<=8 words what is in the frame\"}}\n"
        f"heavy_text=true if the chosen frame has large burned-in caption/subtitle text. "
        f"illustrates=true only if the frame passes the muted test for THIS beat.")
    try:
        r = claude_p(prompt, VISION_MODEL, tools="Read", timeout=120)
    except Exception:
        return None
    if not isinstance(r, dict) or "seconds" not in r:
        return None
    try:
        r["seconds"] = int(float(r["seconds"]))
    except Exception:
        return None
    return r


def _is_playable(path: Path) -> bool:
    try:
        r = subprocess.run(
            ["ffprobe", "-v", "error", "-select_streams", "v:0",
             "-show_entries", "stream=codec_name", "-of", "csv=p=0", str(path)],
            capture_output=True, text=True, timeout=20)
        return r.returncode == 0 and r.stdout.strip() != ""
    except Exception:
        return False


def _extract(video_id: str, center: float, want: float, dur: float) -> str | None:
    """Quality (≤720p) extract of a `want`-second window centred on the chosen moment."""
    try:
        import yt_dlp
    except Exception:
        return None
    CACHE.mkdir(parents=True, exist_ok=True)
    start = max(0.0, min(center - want / 2, max(0.0, dur - want)))
    end = start + want
    key = hashlib.sha1(f"{video_id}:{start:.1f}:{end:.1f}".encode()).hexdigest()[:14]
    path = CACHE / f"{key}.mp4"
    if path.exists() and path.stat().st_size > 20_000:
        return str(path)
    opts = {"quiet": True, "no_warnings": True,
            "format": "bestvideo[height<=1280][ext=mp4]+bestaudio/best[height<=1280]",
            "outtmpl": str(CACHE / f"{key}.%(ext)s"),
            "download_ranges": lambda i, y: [{"start_time": start, "end_time": end}],
            "force_keyframes_at_cuts": True, "merge_output_format": "mp4",
            "socket_timeout": 30, "retries": 2, "noprogress": True}
    try:
        with yt_dlp.YoutubeDL(opts) as y:
            y.download([f"https://www.youtube.com/watch?v={video_id}"])
    except Exception:
        for f in CACHE.glob(f"{key}.*"):
            f.unlink(missing_ok=True)
        return None
    if not path.exists():
        alt = next((p for p in CACHE.glob(f"{key}.*")), None)
        if alt:
            path = alt
    return str(path) if path.exists() and _is_playable(path) else None


def _passes(pick: dict, want_product: bool, min_match: float) -> bool:
    """TOGE muted-test gate: the clip must ILLUSTRATE this exact beat. Faces are fine
    (reaction/demonstration footage is the point). Extra rules: a product beat must not
    show a different product, and no frame with large burned-in captions (they collide
    with the captions we render ourselves)."""
    if not pick or not pick.get("illustrates"):
        return False
    if want_product and pick.get("wrong_product"):
        return False
    if pick.get("heavy_text"):
        return False
    return float(pick.get("match", 0)) >= min_match


def _find(requirement: str, product_name: str | None, want: float,
          min_match: float = 0.55, exclude: set | None = None) -> dict | None:
    """Full muted-test vision pipeline for one narration beat. `exclude` is a set of
    source video ids already used in this video — skip them so beats don't reuse the
    same clip (MMR-style diversity; fixes 'shots 2 & 5 are the same video')."""
    want_product = bool(product_name)
    exclude = exclude or set()
    for cand in _search(_queries(requirement, product_name), n=6):
        if cand["id"] in exclude:
            continue
        proxy = _proxy_download(cand["id"])
        if not proxy:
            continue
        sheet = _contact_sheet(proxy, cand["id"], cand["duration"])
        if not sheet:
            continue
        pick = _vision_pick(sheet, requirement, product_name)
        if not pick:
            continue
        if not _passes(pick, want_product, min_match):
            _log_reject(requirement, cand, pick)
            continue
        clip = _extract(cand["id"], float(pick["seconds"]), want, cand["duration"])
        if clip:
            return {"file": clip, "id": cand["id"], "source": cand["platform"],
                    "url": cand["url"], "title": cand["title"], "ts": pick.get("ts"),
                    "match": pick.get("match"), "seen": pick.get("seen"),
                    "why": f"muted-test “{requirement[:50]}” (match {pick.get('match')}, "
                           f"seen: {pick.get('seen')})"}
    return None


def _log_reject(requirement: str, cand: dict, pick: dict) -> None:
    import sys
    print(f"[footage] reject {cand['id']} for “{requirement[:40]}”: "
          f"seen={pick.get('seen')!r} illustrates={pick.get('illustrates')} "
          f"wrong_product={pick.get('wrong_product')} match={pick.get('match')}",
          file=sys.stderr, flush=True)


def probe(requirement: str, product_name: str | None = None) -> dict:
    """Lightweight AVAILABILITY check for the topic feasibility gate: does real footage
    that ILLUSTRATES this beat exist? Runs search → proxy → contact sheet → vision, but
    SKIPS the high-res extract (cheaper than best_clip). Used to reject stories whose
    key beats have no footage BEFORE we spend a script + render on them."""
    for cand in _search(_queries(requirement, product_name), n=3):
        proxy = _proxy_download(cand["id"])
        if not proxy:
            continue
        sheet = _contact_sheet(proxy, cand["id"], cand["duration"])
        if not sheet:
            continue
        pick = _vision_pick(sheet, requirement, product_name)
        if (pick and pick.get("illustrates")
                and not (product_name and pick.get("wrong_product"))):
            return {"available": True, "match": pick.get("match"),
                    "seen": pick.get("seen"), "url": cand["url"]}
    return {"available": False}


def best_clip(query: str, want_seconds: float = 7.0,
              product_name: str | None = None, exclude: set | None = None) -> dict | None:
    """AUTO path: best vision-matched real video clip for a shot (or None). `exclude` =
    source ids already used in this video (diversity)."""
    return _find(query, product_name, want_seconds, exclude=exclude)


def shortlist(query: str, want_seconds: float = 7.0, n: int = 4,
              product_name: str | None = None) -> list[dict]:
    """CURATE path: up to n vision-matched clips for a shot, for the human to pick."""
    out, seen = [], set()
    for cand in _search(_queries(query, product_name), n=n + 4):
        if cand["id"] in seen:
            continue
        seen.add(cand["id"])
        proxy = _proxy_download(cand["id"])
        if not proxy:
            continue
        sheet = _contact_sheet(proxy, cand["id"], cand["duration"])
        pick = _vision_pick(sheet, query, product_name) if sheet else None
        if not pick or not pick.get("shows_subject"):
            continue
        clip = _extract(cand["id"], float(pick.get("seconds", 0)),
                        want_seconds, cand["duration"])
        if clip:
            out.append({"file": clip, "source": cand["platform"], "url": cand["url"],
                        "title": cand["title"], "ts": pick.get("ts"),
                        "why": f"vision-matched “{_core_terms(query)}”"})
        if len(out) >= n:
            break
    return out
