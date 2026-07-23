"""Stage 4 — FFmpeg render: 1080x1920, animated gradient background, Thai captions.

All on-screen text goes through libass (subtitles filter) — it shapes Thai
correctly; ffmpeg drawtext does not. Template v1 = clean-card (no external
assets needed). B-roll / product-image templates land with the Shopee feed
(needs image URLs + Pexels key).
"""
import random
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FONTS_DIR = ROOT / "assets" / "fonts"  # bundled Noto Sans Thai (OFL) — same on mac/gotham
FONT = "Noto Sans Thai"

# rough chars-per-line for each style (1080px minus margins, Thai avg ~0.55em advance)
WRAP_CHARS = {"Hook": 16, "Body": 22}

# dark two-tone palettes for the animated gradient background (0xRRGGBB)
PALETTES = [
    ("0x0f1020", "0x2a1a3e"),
    ("0x101820", "0x1f3a35"),
    ("0x1a1206", "0x3a2a12"),
]

ASS_HEADER = f"""[Script Info]
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920
WrapStyle: 0

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, OutlineColour, BackColour, Bold, Outline, Shadow, Alignment, MarginL, MarginR, MarginV
Style: Hook,{FONT},92,&H004DD3FC,&H00000000,&H00000000,-1,5,0,5,60,60,0
Style: Body,{FONT},68,&H00FFFFFF,&H00000000,&H00000000,-1,4,0,5,60,60,0

[Events]
Format: Layer, Start, End, Style, Text
"""


def _ts(sec: float) -> str:
    h, rem = divmod(sec, 3600)
    m, s = divmod(rem, 60)
    return f"{int(h)}:{int(m):02d}:{s:05.2f}"


def _wrap(text: str, max_chars: int) -> str:
    """Thai has no spaces, so libass can't line-break it — segment words with
    pythainlp and insert explicit \\N breaks."""
    from pythainlp.tokenize import word_tokenize
    lines, cur = [], ""
    for tok in word_tokenize(text.replace("\n", " "), engine="newmm"):
        if cur and len(cur) + len(tok) > max_chars:
            lines.append(cur)
            cur = tok.strip()
        else:
            cur += tok
    if cur:
        lines.append(cur)
    return "\\N".join(l.strip() for l in lines if l.strip())


def build_ass(timings: list[dict], out: Path):
    events = []
    for i, t in enumerate(timings):
        style = "Hook" if i == 0 else "Body"
        text = _wrap(t["text"], WRAP_CHARS[style])
        events.append(
            f"Dialogue: 0,{_ts(t['start'])},{_ts(t['end'] + 0.15)},{style},"
            f"{{\\fad(150,150)}}{text}")
    out.write_text(ASS_HEADER + "\n".join(events) + "\n")


def render(voice_meta: dict, out_dir: Path, template: str = "clean-card") -> Path:
    build_ass(voice_meta["timings"], out_dir / "captions.ass")
    c0, c1 = random.choice(PALETTES)
    dur = voice_meta["duration"] + 0.5
    final = out_dir / "final.mp4"
    # run from out_dir with relative paths — dodges subtitles-filter path escaping
    subprocess.run(
        ["ffmpeg", "-y", "-v", "error",
         "-f", "lavfi",
         "-i", f"gradients=s=1080x1920:c0={c0}:c1={c1}:speed=0.03:r=30:d={dur}",
         "-i", "voice.mp3",
         "-filter_complex", f"[0:v]subtitles=captions.ass:fontsdir={FONTS_DIR}[v]",
         "-map", "[v]", "-map", "1:a",
         "-t", str(dur),
         "-c:v", "libx264", "-preset", "medium", "-crf", "21", "-pix_fmt", "yuv420p",
         "-c:a", "aac", "-b:a", "128k", "-movflags", "+faststart",
         "final.mp4"],
        cwd=out_dir, check=True)
    return final
