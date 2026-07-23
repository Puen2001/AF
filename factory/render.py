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
]

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
    for chunk in _chunks(words):
        style = "Hook" if chunk[0]["seg"] == "hook" else "Body"
        chunk_end = chunk[-1]["end"] + 0.15
        # one event per word: whole chunk drawn, active word yellow + scaled
        for i, w in enumerate(chunk):
            start = w["start"] if i else chunk[0]["start"]
            end = chunk[i + 1]["start"] if i + 1 < len(chunk) else chunk_end
            text = "".join(
                (r"{\c" + HILITE + r"\fscx110\fscy110}" + x["text"]
                 + r"{\c" + WHITE + r"\fscx100\fscy100}") if j == i else x["text"]
                for j, x in enumerate(chunk))
            events.append(
                f"Dialogue: 0,{_ts(start)},{_ts(end)},{style},{text}")
    out.write_text(ASS_HEADER + "\n".join(events) + "\n")


def render(voice_meta: dict, out_dir: Path, template: str = "clean-card") -> Path:
    build_ass(voice_meta["words"], out_dir / "captions.ass")
    c0, c1 = random.choice(PALETTES)
    dur = voice_meta["duration"] + 0.5
    subprocess.run(
        ["ffmpeg", "-y", "-v", "error",
         "-f", "lavfi",
         "-i", f"gradients=s=1080x1920:c0={c0}:c1={c1}:speed=0.03:r=30:d={dur}",
         "-i", "voice.mp3",
         "-filter_complex",
         f"[0:v]subtitles=captions.ass:fontsdir={FONTS_DIR}[v];"
         "[1:a]loudnorm=I=-14:TP=-1.5:LRA=11[a]",
         "-map", "[v]", "-map", "[a]",
         "-t", str(dur),
         "-c:v", "libx264", "-preset", "medium", "-crf", "21", "-pix_fmt", "yuv420p",
         "-c:a", "aac", "-b:a", "128k", "-movflags", "+faststart",
         "final.mp4"],
        cwd=out_dir, check=True)
    return out_dir / "final.mp4"
