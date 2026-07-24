#!/usr/bin/env python3
"""PANDA STORY-style 'found-clip story' mode (experiment).

Footage-FIRST (reverse of the normal pipeline): find ONE compelling real viral clip,
let Claude WATCH it and write a Thai narration that reframes/dramatizes what's on
screen ("มองเผิน ๆ…แต่จริง ๆ…"), voice it, and render the hero clip playing under
animated captions. No beat-by-beat b-roll — the clip is the star, so the footage-sync
problem disappears.

Usage: python panda_run.py ["search query for a hero clip"]
"""
import json
import subprocess
import sys
from pathlib import Path

import yaml

from factory import db, footage, remotion_render, render, voice
from factory.llm import claude_p

ROOT = Path(__file__).resolve().parent

# genres of inherently-watchable real clips (oddly-satisfying / skill / surprising)
DEFAULT_QUERIES = [
    "oddly satisfying factory production line workers fast",
    "amazing craftsmanship skill worker satisfying",
    "incredible talent street performance crowd reaction",
]

NARRATE_PROMPT = """Use the Read tool to open the image at {sheet}. It is a grid of frames
(with timestamps) from ONE real short video clip.

You are a viral short-form NARRATOR who speaks OVER amazing real clips and reframes an
ordinary moment into something fascinating (think the "you'd never guess what's really
happening here" style). Write an ENGLISH voice-over for THIS clip that keeps a US/global
viewer watching to the very end:
- Open with a REFRAME HOOK (first 2 seconds): make the footage look surprising / curious
  ("It looks like she's just resting — but what's really happening will blow your mind",
  or a bold question). Never start with "In this video".
- Narrate what's actually happening in the clip + add the meaning / backstory / emotion /
  clever detail viewers wouldn't notice on their own.
- End on a payoff that lands: wow / aha / heartwarming.
- Conversational, a friend telling you something cool. No hard sell, no hashtags.
- Total ~{wtarget} words (the clip is ~{dur} seconds of speaking).

Reply ONLY JSON:
{{"seen": "<what is in the clip, short>",
  "hook": "one opening line (the reframe hook)",
  "lines": ["next line", "...", "final payoff line"]}}"""

EN_VOICE = "en-US-AndrewNeural"   # natural US storytelling voice (edge-tts)


def _download_full(video_id: str, dst: Path) -> bool:
    try:
        import yt_dlp
    except Exception:
        return False
    opts = {"quiet": True, "no_warnings": True, "noprogress": True,
            "format": "bestvideo[height<=1280][ext=mp4]+bestaudio/best[height<=1280]",
            "outtmpl": str(dst.with_suffix("")) + ".%(ext)s",
            "merge_output_format": "mp4", "socket_timeout": 30, "retries": 2}
    try:
        with yt_dlp.YoutubeDL(opts) as y:
            y.download([f"https://www.youtube.com/watch?v={video_id}"])
    except Exception:
        return False
    return dst.exists()


def _dur(path: Path) -> float:
    try:
        r = subprocess.run(["ffprobe", "-v", "error", "-show_entries",
                            "format=duration", "-of", "default=nk=1:nw=1", str(path)],
                           capture_output=True, text=True, timeout=20)
        return float(r.stdout.strip())
    except Exception:
        return 0.0


def find_hero(query: str, vdir: Path) -> dict | None:
    """Find + download ONE compelling real clip (15-75s) and confirm it's watchable."""
    for cand in footage._search([query], n=6):
        if not (12 <= cand["duration"] <= 75):
            continue
        dst = vdir / "hero.mp4"
        if not _download_full(cand["id"], dst):
            continue
        d = _dur(dst)
        if d < 8:
            continue
        return {"file": str(dst), "dur": d, "id": cand["id"],
                "url": cand["url"], "title": cand["title"]}
    return None


def main(query: str | None):
    cfg = yaml.safe_load((ROOT / "config" / "config.yaml").read_text())
    conn = db.connect()
    vdir = ROOT / "queue" / "panda1"
    vdir.mkdir(parents=True, exist_ok=True)

    queries = [query] if query else DEFAULT_QUERIES
    hero = None
    for q in queries:
        print(f"[panda] searching hero clip: {q}", flush=True)
        hero = find_hero(q, vdir)
        if hero:
            break
    if not hero:
        print("[panda] no hero clip found", flush=True)
        return
    print(f"[panda] HERO: {hero['title'][:50]} ({hero['dur']:.0f}s) {hero['url']}", flush=True)

    # narration target ~80% of clip length so the clip covers the voice
    tdur = min(hero["dur"] - 2, 32)
    wtarget = int(tdur * 2.3)   # ~2.3 English words/sec spoken
    sheet = footage._contact_sheet(hero["file"], "panda_hero", hero["dur"])
    print("[panda] Claude watching clip + writing narration...", flush=True)
    body = claude_p(NARRATE_PROMPT.format(sheet=sheet, wtarget=wtarget,
                                          dur=int(hero["dur"])),
                    cfg.get("model", "sonnet"), tools="Read", timeout=150)
    print(f"[panda] seen: {body.get('seen')}", flush=True)
    print(f"[panda] hook: {body.get('hook')}", flush=True)

    print("[panda] voice (English)...", flush=True)
    meta = voice.synth(body["hook"], body["lines"], EN_VOICE, vdir, rate="+0%")
    render.build_ass(meta["words"], vdir / "captions.ass")

    # ONE hero shot spanning the whole narration (clip is the star, no beat cuts)
    shots = [{"file": hero["file"], "type": "hero", "from": 0,
              "to": len(body["lines"])}]
    print(f"[panda] render via Remotion (voice {meta['duration']:.0f}s under hero clip)...",
          flush=True)
    mp4 = remotion_render.render(meta, vdir, body=body, shots=shots, cfg=cfg)
    import os
    print(f"[panda] DONE: {mp4} ({os.path.getsize(mp4)//1024}KB)", flush=True)


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else None)
