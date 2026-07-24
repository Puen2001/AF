#!/usr/bin/env python3
"""Re-render an existing script through Remotion (animated captions). Usage:
python rerender_remotion.py <script_id>"""
import json
import sys
from pathlib import Path

import yaml

from factory import broll, db, remotion_render, render, voice

ROOT = Path(__file__).resolve().parent


def main(sid: int):
    cfg = yaml.safe_load((ROOT / "config" / "config.yaml").read_text())
    conn = db.connect()
    row = conn.execute("SELECT * FROM scripts WHERE id=?", (sid,)).fetchone()
    body = json.loads(row["body"])
    prod = body.get("product") or {}
    pname = prod.get("search") or prod.get("category") or prod.get("name")
    vdir = ROOT / cfg["paths"]["queue"] / f"s{sid}_remotion"
    vdir.mkdir(parents=True, exist_ok=True)

    print(f"[re] script {sid}: {body.get('hook','')[:50]}", flush=True)
    print("[re] voice...", flush=True)
    meta = voice.synth(body["hook"], body["lines"], cfg["voice"]["primary"], vdir,
                       rate=cfg["voice"].get("rate", "+0%"))
    print(f"[re] footage (muted-test, product={pname!r})...", flush=True)
    shots = broll.resolve(body.get("shots", []), cfg, product_name=pname)
    print(f"[re] {sum(1 for s in shots if s.get('file'))}/{len(shots)} beats matched",
          flush=True)
    render.build_ass(meta["words"], vdir / "captions.ass")
    print("[re] Remotion render (animated captions)...", flush=True)
    mp4 = remotion_render.render(meta, vdir, body=body, shots=shots, cfg=cfg)
    import os
    print(f"[re] DONE: {mp4} ({os.path.getsize(mp4)//1024}KB)", flush=True)


if __name__ == "__main__":
    main(int(sys.argv[1]))
