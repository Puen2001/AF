#!/usr/bin/env python3
"""One-off driver: script + produce a specific product through the STRICT footage
engine, so we can test the new system on a fresh product without the director's
rotation. Usage: python fan_run.py <product_id>"""
import json
import sys
from pathlib import Path

import yaml

from factory import broll, db, render, scriptgen, voice

ROOT = Path(__file__).resolve().parent


def main(pid: int):
    cfg = yaml.safe_load((ROOT / "config" / "config.yaml").read_text())
    conn = db.connect()
    product = conn.execute("SELECT * FROM products WHERE id=?", (pid,)).fetchone()
    print(f"[fan] product: {product['name']}", flush=True)

    print("[fan] script ladder (3 drafts -> judge -> polish -> fact-check)...", flush=True)
    r = scriptgen.generate_one(conn, product, cfg)
    print(f"[fan] scriptgen: {json.dumps(r, ensure_ascii=False)[:300]}", flush=True)

    row = conn.execute(
        "SELECT s.* FROM scripts s LEFT JOIN videos v ON v.script_id=s.id "
        "WHERE s.product_id=? AND s.status='checked' AND v.id IS NULL "
        "ORDER BY s.id DESC LIMIT 1", (pid,)).fetchone()
    if not row:
        print("[fan] no checked script produced — stopping", flush=True)
        return
    body = json.loads(row["body"])
    vdir = ROOT / cfg["paths"]["queue"] / f"s{row['id']}"
    vdir.mkdir(parents=True, exist_ok=True)

    print("[fan] voice...", flush=True)
    meta = voice.synth(body["hook"], body["lines"], cfg["voice"]["primary"], vdir,
                       rate=cfg["voice"].get("rate", "+0%"))
    prod = body.get("product") or {}
    print("[fan] STRICT footage resolve (vision-guided, exact-product)...", flush=True)
    shots = broll.resolve(body.get("shots", []), cfg,
                          product_media=prod.get("media"),
                          product_name=prod.get("name") or product["name"])
    matched = sum(1 for s in shots if s.get("file"))
    for i, s in enumerate(shots):
        print(f"[fan] shot {i} type={s.get('type')} "
              f"{'VIDEO ' + str(s.get('source')) if s.get('file') else 'NO-MATCH (card)'} "
              f"{s.get('ref','')}", flush=True)
    print(f"[fan] {matched}/{len(shots)} shots matched real footage", flush=True)

    print("[fan] render...", flush=True)
    mp4 = render.render(meta, vdir, body=body, shots=shots)
    conn.execute("INSERT INTO videos (script_id, template, file, status, created_at) "
                 "VALUES (?,?,?,?,?)", (row["id"], "strict", str(mp4), "rendered", db.now()))
    conn.commit()
    import os
    print(f"[fan] DONE: {mp4} ({os.path.getsize(mp4)//1024}KB) script={row['id']}", flush=True)


if __name__ == "__main__":
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 13)
