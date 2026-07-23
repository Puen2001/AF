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
from factory import db, discover, scriptgen  # noqa: E402

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

    # TODO phase 2: voice.run(), render.run()
    # TODO phase 3: approve.run(), publish.run()
    print(json.dumps(db.counts(conn), indent=2))


if __name__ == "__main__":
    main()
