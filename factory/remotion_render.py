"""Stage 4 (alt) — RENDER via Remotion (React code→video) instead of ffmpeg.

Why: ffmpeg tops out at hard-cuts + static captions; DaVinci scripting is Studio-only
(free blocks it). Remotion renders headless from code, so it gives content-grade
animated word-by-word captions, punch-ins, transitions, and motion — fully automatable.

Drop-in for render.render(voice_meta, out_dir, body, shots, cfg): stages the produced
assets (voice, per-shot clips, music) into remotion/public/render/<id>/, writes a
props.json the <Short> composition consumes, and shells out to `remotion render`.
"""
import json
import shutil
import subprocess
from pathlib import Path

from . import render as ff  # reuse _segments_from_shots (narration-accurate timing)

ROOT = Path(__file__).resolve().parent.parent
REMOTION = ROOT / "remotion"
PUBLIC = REMOTION / "public"
FPS = 30


def available() -> bool:
    return (REMOTION / "package.json").exists() and (REMOTION / "node_modules").exists()


def render(voice_meta: dict, out_dir: Path, body: dict | None = None,
           shots: list[dict] | None = None, cfg: dict | None = None) -> Path:
    body = body or {}
    dur = voice_meta["duration"] + 0.5
    spans = voice_meta.get("line_spans", [])
    segs = (ff._segments_from_shots(shots, spans, dur)
            if shots and any(s.get("file") for s in shots) and spans
            else [{"len": dur, "file": None, "card": True}])

    rid = out_dir.name
    stage = PUBLIC / "render" / rid
    if stage.exists():
        shutil.rmtree(stage)
    (stage / "shots").mkdir(parents=True, exist_ok=True)

    # stage voice
    shutil.copy(out_dir / "voice.mp3", stage / "voice.mp3")
    # stage music (first track in assets/music, if any)
    music_rel = None
    mdir = ROOT / "assets" / "music"
    tracks = sorted(mdir.glob("*.[mw][pa][3v]")) if mdir.exists() else []
    if tracks:
        shutil.copy(tracks[0], stage / "music.mp3")
        music_rel = f"render/{rid}/music.mp3"

    # stage per-shot clips → props segments (frames from narration span)
    out_shots, acc = [], 0
    for i, seg in enumerate(segs):
        frames = max(int(round(seg["len"] * FPS)), 1)
        rel = None
        if seg.get("file"):
            ext = Path(seg["file"]).suffix or ".mp4"
            dst = stage / "shots" / f"{i}{ext}"
            try:
                shutil.copy(seg["file"], dst)
                rel = f"render/{rid}/shots/{i}{ext}"
            except Exception:
                rel = None
        out_shots.append({"file": rel, "from": acc, "frames": frames})
        acc += frames

    props = {
        "fps": FPS, "width": 1080, "height": 1920,
        "durationInFrames": max(acc, 1),
        "voice": f"render/{rid}/voice.mp3",
        "music": music_rel,
        "words": [{"text": w["text"], "start": w["start"], "end": w["end"]}
                  for w in voice_meta.get("words", [])],
        "shots": out_shots,
        "hook": body.get("hook", ""),
    }
    props_path = stage / "props.json"
    props_path.write_text(json.dumps(props, ensure_ascii=False))

    out_file = out_dir / "final.mp4"
    cmd = ["npx", "remotion", "render", "Short", str(out_file),
           f"--props={props_path}", "--concurrency=4",
           "--log=error"]
    subprocess.run(cmd, cwd=REMOTION, check=True)
    return out_file
