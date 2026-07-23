"""Stage 3 — TTS via edge-tts (free Microsoft neural voices).

Synthesizes each line separately so per-line durations become caption timings,
then concatenates with a small pause after every line.
"""
import asyncio
import json
import subprocess
from pathlib import Path

import edge_tts

GAP = 0.3  # seconds of silence after each line


def _duration(path: Path) -> float:
    out = subprocess.run(
        ["ffprobe", "-v", "quiet", "-show_entries", "format=duration",
         "-of", "csv=p=0", str(path)],
        capture_output=True, text=True, check=True)
    return float(out.stdout.strip())


async def _synth_line(text: str, voice: str, out: Path):
    await edge_tts.Communicate(text, voice).save(str(out))


def synth(lines: list[str], voice: str, out_dir: Path) -> dict:
    out_dir.mkdir(parents=True, exist_ok=True)
    parts = []
    for i, text in enumerate(lines):
        part = out_dir / f"part{i:02d}.mp3"
        asyncio.run(_synth_line(text, voice, part))
        parts.append(part)

    timings, t = [], 0.0
    for part, text in zip(parts, lines):
        d = _duration(part)
        timings.append({"text": text, "start": round(t, 2), "end": round(t + d, 2)})
        t += d + GAP

    # decode-concat with a trailing pad per line (robust across codec params)
    cmd = ["ffmpeg", "-y", "-v", "error"]
    for part in parts:
        cmd += ["-i", str(part)]
    fc = "".join(f"[{i}:a]apad=pad_dur={GAP}[a{i}];" for i in range(len(parts)))
    fc += "".join(f"[a{i}]" for i in range(len(parts)))
    fc += f"concat=n={len(parts)}:v=0:a=1[out]"
    audio = out_dir / "voice.mp3"
    cmd += ["-filter_complex", fc, "-map", "[out]", str(audio)]
    subprocess.run(cmd, check=True)

    meta = {"audio": str(audio), "timings": timings, "duration": round(t, 2)}
    (out_dir / "timings.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1))
    return meta
