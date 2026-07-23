"""F5-TTS-THAI voice-clone backend (local, GPU — gotham). Optional alternative to
edge-tts; clones a target voice zero-shot from one short reference clip.

Setup on gotham (has the GPU):
  pip install f5-tts   # or clone VIZINTZOR/F5-TTS-THAI
  # put a clean ~30s Thai reference clip at assets/voice/ref.wav
  # set its transcript in config voice.ref_text, and voice.provider: f5-clone

Zero-shot: no training — F5 conditions on (ref_audio, ref_text) to speak new text
in that voice. CC-BY-4.0 (attribute). CPU works but is slow; batch-render offline.

Returns [] for word timings (F5 emits no word events); render.py estimates caption
timing proportionally from line length, same path as any non-edge-tts backend.
"""
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def synth_line(text: str, out: Path, cfg: dict) -> list[dict]:
    ref_audio = ROOT / cfg.get("ref_audio", "assets/voice/ref.wav")
    ref_text = cfg.get("ref_text", "")
    if not ref_audio.exists() or not ref_text:
        raise RuntimeError(
            "f5-clone needs a reference clip + transcript: put a ~30s Thai sample at "
            f"{ref_audio} and set voice.ref_text. See factory/voice_f5.py header.")
    # F5-TTS-THAI CLI (adjust to the installed entrypoint on gotham)
    subprocess.run(
        ["f5-tts_infer-cli", "--model", "F5-TTS",
         "--ref_audio", str(ref_audio), "--ref_text", ref_text,
         "--gen_text", text, "--output", str(out)],
        check=True, timeout=600)
    return []  # no word-level events; timings estimated downstream
