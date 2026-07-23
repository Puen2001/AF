"""Stage 3 — TTS via edge-tts (free Microsoft neural voices), word-timed.

Two synthesis calls: the hook alone (it's a standalone punch line) and the whole
body as ONE call — continuous prosody instead of a per-line reset — joined with a
short gap. WordBoundary events give per-word offsets for karaoke captions; keeping
hook and body as separate calls means no fragile text alignment (Azure normalizes
numbers etc., so token text can't be matched back to written lines reliably).
"""
import asyncio
import json
import subprocess
from pathlib import Path

import edge_tts

GAP = 0.35  # silence between hook and body


def _duration(path: Path) -> float:
    out = subprocess.run(
        ["ffprobe", "-v", "quiet", "-show_entries", "format=duration",
         "-of", "csv=p=0", str(path)],
        capture_output=True, text=True, check=True)
    return float(out.stdout.strip())


async def _synth(text: str, voice: str, rate: str, out: Path) -> list[dict]:
    comm = edge_tts.Communicate(text, voice, rate=rate, boundary="WordBoundary")
    words = []
    with open(out, "wb") as f:
        async for chunk in comm.stream():
            if chunk["type"] == "audio":
                f.write(chunk["data"])
            elif chunk["type"] == "WordBoundary":
                words.append({"text": chunk["text"],
                              "start": chunk["offset"] / 1e7,
                              "end": (chunk["offset"] + chunk["duration"]) / 1e7})
    return words


def _synth_backend(text: str, voice: str, rate: str, out: Path,
                   cfg: dict | None = None) -> list[dict]:
    """Dispatch to the configured TTS provider. edge-tts returns word timings
    directly; f5-clone (local voice clone) has no word events, so timings are
    estimated proportionally downstream."""
    provider = (cfg or {}).get("provider", "edge-tts")
    if provider == "f5-clone":
        from . import voice_f5
        return voice_f5.synth_line(text, out, cfg)
    return asyncio.run(_synth(text, voice, rate, out))


def synth(hook: str, body_lines: list[str], voice: str, out_dir: Path,
          rate: str = "+0%", cfg: dict | None = None) -> dict:
    out_dir.mkdir(parents=True, exist_ok=True)
    hook_mp3, body_mp3 = out_dir / "hook.mp3", out_dir / "body.mp3"

    hook_words = _synth_backend(hook, voice, rate, hook_mp3, cfg)
    body_words = _synth_backend(". ".join(body_lines), voice, rate, body_mp3, cfg)

    hook_dur = _duration(hook_mp3)
    offset = hook_dur + GAP
    words = ([{**w, "seg": "hook"} for w in hook_words] +
             [{"text": w["text"], "start": w["start"] + offset,
               "end": w["end"] + offset, "seg": "body"} for w in body_words])

    audio = out_dir / "voice.mp3"
    subprocess.run(
        ["ffmpeg", "-y", "-v", "error", "-i", str(hook_mp3), "-i", str(body_mp3),
         "-filter_complex",
         f"[0:a]apad=pad_dur={GAP}[h];[h][1:a]concat=n=2:v=0:a=1[out]",
         "-map", "[out]", str(audio)],
        check=True)

    meta = {"audio": str(audio), "words": words,
            "duration": round(_duration(audio), 2)}
    (out_dir / "timings.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1))
    return meta
