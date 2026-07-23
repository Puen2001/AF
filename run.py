#!/usr/bin/env python3
"""Orchestrator. Usage:
  python run.py daily [--limit N]   discover + script (voice/render/approve as they land)
  python run.py dry-run             one product through every built stage, verbose
  python run.py status              pipeline counts
"""
import argparse
import json
import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))
from factory import db, discover, render, scriptgen, voice  # noqa: E402

ROOT = Path(__file__).resolve().parent


def load_cfg() -> dict:
    return yaml.safe_load((ROOT / "config" / "config.yaml").read_text())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("command", choices=["daily", "dry-run", "status"])
    ap.add_argument("--limit", type=int, default=None)
    args = ap.parse_args()

    cfg = load_cfg()
    conn = db.connect()

    if args.command == "status":
        print(json.dumps(db.counts(conn), indent=2))
        return

    limit = args.limit or (1 if args.command == "dry-run" else cfg["daily_quota"])

    d = discover.run(conn)
    print(f"[discover] {d}")

    for r in scriptgen.run(conn, cfg, limit=limit):
        print(f"[scriptgen] {json.dumps(r, ensure_ascii=False)}")

    # produce: checked scripts that have no video yet → voice + render
    pending = conn.execute(
        "SELECT s.* FROM scripts s LEFT JOIN videos v ON v.script_id = s.id "
        "WHERE s.status='checked' AND v.id IS NULL ORDER BY s.id LIMIT ?",
        (limit,)).fetchall()
    for s in pending:
        body = json.loads(s["body"])
        vdir = ROOT / cfg["paths"]["queue"] / f"s{s['id']}"
        try:
            meta = voice.synth([body["hook"], *body["lines"]],
                               cfg["voice"]["primary"], vdir)
            mp4 = render.render(meta, vdir)
            conn.execute(
                "INSERT INTO videos (script_id, template, file, status, created_at) "
                "VALUES (?,?,?,?,?)",
                (s["id"], "clean-card", str(mp4), "rendered", db.now()))
            conn.commit()
            print(f"[produce] script {s['id']} → {mp4} ({meta['duration']}s)")
        except Exception as e:
            print(f"[produce] script {s['id']} FAILED: {e}")

    # TODO phase 3: approve.run(), publish.run()
    print(json.dumps(db.counts(conn), indent=2))


if __name__ == "__main__":
    main()
