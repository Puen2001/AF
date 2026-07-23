"""Stage 4 — FFmpeg render: 1080x1920, animated gradient background, karaoke captions.

Captions are short word-chunks (2-4 Thai words) that replace each other, with the
currently-spoken word highlighted yellow and slightly scaled — driven by edge-tts
WordBoundary timings, no ASR. All text goes through libass (bundled Noto Sans Thai);
ffmpeg drawtext can't shape Thai. Voice track is loudness-normalized to -14 LUFS
(platform standard).
"""
import random
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FONTS_DIR = ROOT / "assets" / "fonts"
FONT = "Noto Sans Thai"

HILITE = r"&H004DD3FC&"   # #FCD34D yellow (ASS BGR)
WHITE = r"&HFFFFFF&"

# chunk size in Thai chars per style; > gap seconds forces a chunk break
CHUNK_CHARS = {"hook": 10, "body": 14}
CHUNK_GAP = 0.6

PALETTES = [
    ("0x0f1020", "0x2a1a3e"),
    ("0x101820", "0x1f3a35"),
    ("0x1a1206", "0x3a2a12"),
    ("0x0d1b2a", "0x1b3a4b"),
    ("0x1a0f1f", "0x3d1f47"),
    ("0x141414", "0x2e2620"),
]

SCENE_LEN = 6.0   # background scene length before a crossfade cut
XFADE = 0.5

ASS_HEADER = f"""[Script Info]
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920
WrapStyle: 2

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, OutlineColour, BackColour, Bold, Outline, Shadow, Alignment, MarginL, MarginR, MarginV
Style: Hook,{FONT},96,&H00FFFFFF,&H00000000,&H00000000,-1,5,0,5,40,40,0
Style: Body,{FONT},72,&H00FFFFFF,&H00000000,&H00000000,-1,4,0,5,40,40,0

[Events]
Format: Layer, Start, End, Style, Text
"""


def _ts(sec: float) -> str:
    h, rem = divmod(max(sec, 0), 3600)
    m, s = divmod(rem, 60)
    return f"{int(h)}:{int(m):02d}:{s:05.2f}"


def _chunks(words: list[dict]) -> list[list[dict]]:
    groups, cur = [], []
    for w in words:
        gap = w["start"] - cur[-1]["end"] if cur else 0
        full = cur and (sum(len(x["text"]) for x in cur) + len(w["text"])
                        > CHUNK_CHARS[cur[0]["seg"]])
        if cur and (full or gap > CHUNK_GAP or w["seg"] != cur[0]["seg"]):
            groups.append(cur)
            cur = []
        cur.append(w)
    if cur:
        groups.append(cur)
    return groups


def build_ass(words: list[dict], out: Path):
    events = []
    groups = _chunks(words)
    for g, chunk in enumerate(groups):
        style = "Hook" if chunk[0]["seg"] == "hook" else "Body"
        # display padding must never overlap the next chunk (two captions at once)
        chunk_end = chunk[-1]["end"] + 0.15
        if g + 1 < len(groups):
            chunk_end = min(chunk_end, groups[g + 1][0]["start"])
        # ". " joins lines for TTS pausing — never show that punctuation
        texts = [w["text"].strip(".,!?") for w in chunk]
        # one event per word: whole chunk drawn, active word yellow + scaled;
        # the chunk's first event gets an entrance pop instead of per-word scale
        for i, w in enumerate(chunk):
            start = w["start"] if i else chunk[0]["start"]
            end = chunk[i + 1]["start"] if i + 1 < len(chunk) else chunk_end
            if end <= start:
                continue
            if i == 0:
                pop = r"{\fscx86\fscy86\t(0,120,\fscx100\fscy100)\fad(60,0)}"
                text = pop + "".join(
                    (r"{\c" + HILITE + r"}" + t + r"{\c" + WHITE + r"}")
                    if j == 0 else t
                    for j, t in enumerate(texts))
            else:
                text = "".join(
                    (r"{\c" + HILITE + r"\fscx110\fscy110}" + t
                     + r"{\c" + WHITE + r"\fscx100\fscy100}") if j == i else t
                    for j, t in enumerate(texts))
            events.append(
                f"Dialogue: 0,{_ts(start)},{_ts(end)},{style},{text}")
    out.write_text(ASS_HEADER + "\n".join(events) + "\n")


def _segments_from_shots(shots: list[dict], body: dict, words: list[dict],
                         dur: float) -> list[dict]:
    """Map the shot plan (line ranges) to time segments via proportional
    line lengths — b-roll cuts don't need frame-exact sync."""
    hook_words = [w for w in words if w["seg"] == "hook"]
    hook_end = (hook_words[-1]["end"] + 0.3) if hook_words else 0.0
    lines = body.get("lines", [])
    total = sum(len(l) for l in lines) or 1
    bounds, acc = [hook_end], 0
    for l in lines:
        acc += len(l)
        bounds.append(hook_end + (dur - hook_end) * acc / total)

    def line_end(i: int) -> float:  # line 0 = hook
        return hook_end if i <= 0 else bounds[min(i, len(bounds) - 1)]

    segs, t = [], 0.0
    for s in sorted(shots, key=lambda s: int(s.get("from", 0))):
        end = line_end(int(s.get("to", 0)))
        if end <= t + 1.0:
            continue
        segs.append({"len": end - t, "file": s.get("file")})
        t = end
    if t < dur - 0.05:
        segs.append({"len": dur - t, "file": None})
    return segs


def _compose_background(segs: list[dict]) -> tuple[list[str], str]:
    """Segments (licensed clip or gradient scene) crossfaded on exact cumulative
    boundaries — reads as edited cuts, not a static loop."""
    inputs, fc = [], ""
    pals = random.sample(PALETTES, k=len(PALETTES))
    for i, seg in enumerate(segs):
        d = seg["len"] + XFADE
        if seg["file"]:
            inputs += ["-stream_loop", "-1", "-t", f"{d:.2f}", "-i", seg["file"]]
            fc += (f"[{i}:v]scale=1080:1920:force_original_aspect_ratio=increase,"
                   f"crop=1080:1920,fps=30,eq=brightness=-0.06:saturation=0.95,"
                   f"trim=duration={d:.2f},setpts=PTS-STARTPTS[p{i}];")
        else:
            c0, c1 = pals[i % len(pals)]
            x0, y0 = random.randint(0, 540), random.randint(0, 960)
            x1, y1 = random.randint(540, 1079), random.randint(960, 1919)
            inputs += ["-f", "lavfi", "-i",
                       f"gradients=s=1080x1920:c0={c0}:c1={c1}:x0={x0}:y0={y0}:"
                       f"x1={x1}:y1={y1}:speed=0.04:r=30:d={d:.2f}"]
            fc += f"[{i}:v]null[p{i}];"
    if len(segs) == 1:
        return inputs, fc + "[p0]null[bg];"
    prev, cum = "[p0]", 0.0
    for i in range(1, len(segs)):
        cum += segs[i - 1]["len"]
        out = "[bg]" if i == len(segs) - 1 else f"[x{i}]"
        fc += (f"{prev}[p{i}]xfade=transition=fade:duration={XFADE}:"
               f"offset={cum:.2f}{out};")
        prev = out
    return inputs, fc


def render(voice_meta: dict, out_dir: Path, body: dict | None = None,
           shots: list[dict] | None = None) -> Path:
    build_ass(voice_meta["words"], out_dir / "captions.ass")
    dur = voice_meta["duration"] + 0.5

    if shots and any(s.get("file") for s in shots) and body:
        segs = _segments_from_shots(shots, body, voice_meta["words"], dur)
    else:  # gradient scenes only
        n = max(1, round(dur / SCENE_LEN))
        segs = [{"len": dur / n, "file": None} for _ in range(n)]
    bg_inputs, bg_fc = _compose_background(segs)
    n = len(segs)

    voice_idx = n
    cmd = ["ffmpeg", "-y", "-v", "error", *bg_inputs, "-i", "voice.mp3"]

    # optional music bed: drop any licensed track into assets/music/ to activate
    music = sorted((ROOT / "assets" / "music").glob("*.[mw][pa][3v]")) \
        if (ROOT / "assets" / "music").exists() else []
    if music:
        cmd += ["-stream_loop", "-1", "-i", str(random.choice(music))]
        audio_fc = (
            f"[{voice_idx + 1}:a]volume=0.30[m0];"
            f"[m0][{voice_idx}:a]sidechaincompress="
            f"threshold=0.03:ratio=12:attack=15:release=400[duck];"
            f"[{voice_idx}:a][duck]amix=inputs=2:duration=first:normalize=0[mix];"
            f"[mix]loudnorm=I=-14:TP=-1.5:LRA=11[a]")
    else:
        audio_fc = f"[{voice_idx}:a]loudnorm=I=-14:TP=-1.5:LRA=11[a]"

    video_fc = (
        f"{bg_fc}"
        f"[bg]vignette=PI/5,"
        f"drawbox=x=0:y=ih-12:w=iw*t/{dur:.2f}:h=12:color=white@0.45:t=fill,"
        f"subtitles=captions.ass:fontsdir={FONTS_DIR}[v];")

    cmd += ["-filter_complex", video_fc + audio_fc,
            "-map", "[v]", "-map", "[a]",
            "-t", str(dur),
            "-c:v", "libx264", "-preset", "medium", "-crf", "21",
            "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-b:a", "128k", "-movflags", "+faststart",
            "final.mp4"]
    subprocess.run(cmd, cwd=out_dir, check=True)
    return out_dir / "final.mp4"
