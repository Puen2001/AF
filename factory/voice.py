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

GAP = 0.5   # silence between hook and body
LINE_GAP = 0.42  # silence between each body line — breathing room


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
    """Synthesize hook + each body line SEPARATELY and concat with a real pause
    between each — gives breathing room between phrases (operator wants space,
    not a rushed run-on). Word timings accumulate across the gaps."""
    out_dir.mkdir(parents=True, exist_ok=True)
    line_gap = (cfg or {}).get("line_gap", LINE_GAP)

    segments = [("hook", hook)] + [("body", ln) for ln in body_lines]
    parts, words, offset = [], [], 0.0
    for i, (seg, text) in enumerate(segments):
        part = out_dir / f"seg{i:02d}.mp3"
        w = _synth_backend(text, voice, rate, part, cfg)
        for x in w:
            words.append({"text": x["text"], "start": x["start"] + offset,
                          "end": x["end"] + offset, "seg": seg})
        gap = GAP if seg == "hook" else line_gap
        offset += _duration(part) + gap
        parts.append((part, gap))

    audio = out_dir / "voice.mp3"
    cmd = ["ffmpeg", "-y", "-v", "error"]
    for part, _ in parts:
        cmd += ["-i", str(part)]
    fc = "".join(f"[{i}:a]apad=pad_dur={g}[a{i}];" for i, (_, g) in enumerate(parts))
    fc += "".join(f"[a{i}]" for i in range(len(parts)))
    fc += f"concat=n={len(parts)}:v=0:a=1[out]"
    cmd += ["-filter_complex", fc, "-map", "[out]", str(audio)]
    subprocess.run(cmd, check=True)

    meta = {"audio": str(audio), "words": words,
            "duration": round(_duration(audio), 2)}
    (out_dir / "timings.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1))
    return meta
