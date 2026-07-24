#!/usr/bin/env python3
"""Orchestrator. Usage:
  python run.py daily [--limit N]   discover + script (voice/render/approve as they land)
  python run.py dry-run             one product through every built stage, verbose
  python run.py status              pipeline counts
"""
import argparse
import json
import os
import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))
from factory import (approve, broll, curate, db, director, discover,  # noqa: E402
                     publish, render, scriptgen, topics, trends, voice)

ROOT = Path(__file__).resolve().parent


def load_cfg() -> dict:
    return yaml.safe_load((ROOT / "config" / "config.yaml").read_text())


def load_secrets():
    p = ROOT / "config" / "secrets.env"
    if p.exists():
        for line in p.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.split("#")[0].strip())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("command", choices=["daily", "dry-run", "weekly", "status",
                                        "poll", "yt-auth", "curate"])
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--id", type=int, default=None, help="script id for curate")
    args = ap.parse_args()

    cfg = load_cfg()
    load_secrets()
    conn = db.connect()

    if args.command == "status":
        print(json.dumps(db.counts(conn), indent=2))
        return

    if args.command == "weekly":
        print(json.dumps(director.analyze(conn, cfg), ensure_ascii=False, indent=2))
        return

    if args.command == "yt-auth":
        creds = publish.yt_creds(interactive=True)
        print("YouTube auth OK" if creds else "YouTube auth FAILED")
        return

    if args.command == "poll":  # every 15 min via timer: approvals → publish
        handled = approve.poll(conn, cfg)
        posted = publish.process(conn, cfg)
        print(f"[poll] approvals handled: {handled}, published: {posted}")
        return

    if args.command == "curate":  # human-in-the-loop footage picking (interactive)
        row = (conn.execute("SELECT * FROM scripts WHERE id=?", (args.id,)).fetchone()
               if args.id else conn.execute(
               "SELECT s.* FROM scripts s LEFT JOIN videos v ON v.script_id=s.id "
               "WHERE s.status='checked' AND v.id IS NULL ORDER BY s.id DESC LIMIT 1"
               ).fetchone())
        if not row:
            print("no script to curate")
            return
        body = json.loads(row["body"])
        vdir = ROOT / cfg["paths"]["queue"] / f"s{row['id']}"
        prod = body.get("product") or {}
        print("[curate] shortlisting candidates...")
        sl = broll.shortlist(body.get("shots", []), cfg, product_media=prod.get("media"),
                             product_name=prod.get("name"))
        picks = curate.curate(sl)
        shots = [{**sh, "file": f} for sh, f in zip(sl, picks)]
        meta = voice.synth(body["hook"], body["lines"], cfg["voice"]["primary"],
                           vdir, rate=cfg["voice"].get("rate", "+0%"), cfg=cfg["voice"])
        mp4 = render.render(meta, vdir, body=body, shots=shots)
        conn.execute("INSERT INTO videos (script_id, template, file, status, created_at) "
                     "VALUES (?,?,?,?,?)", (row["id"], "curated", str(mp4),
                                            "rendered", db.now()))
        conn.commit()
        print(f"[curate] rendered {mp4}")
        approve.send_pending(conn, cfg)
        return

    limit = args.limit or (1 if args.command == "dry-run" else cfg["daily_quota"])

    if cfg.get("mode") == "story-first":
        # trend → topic → FOOTAGE FEASIBILITY GATE → story (product attached as the
        # natural ending only when it fits). Pick stories the footage can actually tell.
        print(f"[trends] {trends.discover(conn, cfg)}")
        cands = db.rows(conn, "topics", "discovered", 8, order="audience_fit DESC, id")
        ranked = topics.rank(conn, cfg, cands) if cands else []
        for r in ranked[:limit]:
            print(f"[feasibility] {r['score']:.2f} footage={r['feasibility']['score']:.2f} "
                  f"| {r['topic']['title'][:50]}")
        for t in [r["topic"] for r in ranked[:limit]]:
            try:
                r = scriptgen.generate_from_topic(conn, t, cfg)
            except Exception as e:
                r = {"topic": t["title"], "status": "error", "error": str(e)}
            print(f"[story] {json.dumps(r, ensure_ascii=False)}")
    else:
        d = discover.run(conn)
        d["triaged"] = discover.triage(conn, cfg)
        print(f"[discover] {d}")
        picks = director.plan(conn, cfg, limit)
        if picks:
            print(f"[director] {json.dumps(picks, ensure_ascii=False)}")
            for pick in picks:
                product = conn.execute("SELECT * FROM products WHERE id=?",
                                       (pick["product_id"],)).fetchone()
                try:
                    r = scriptgen.generate_one(conn, product, cfg,
                                               suggested_angle=pick.get("angle"))
                except Exception as e:
                    r = {"product": product["name"], "status": "error", "error": str(e)}
                print(f"[scriptgen] {json.dumps(r, ensure_ascii=False)}")
        else:
            for r in scriptgen.run(conn, cfg, limit=limit):
                print(f"[scriptgen] {json.dumps(r, ensure_ascii=False)}")

    # produce: checked scripts that have no video yet → voice + render
    pending = conn.execute(
        "SELECT s.* FROM scripts s LEFT JOIN videos v ON v.script_id = s.id "
        "WHERE s.status='checked' AND v.id IS NULL ORDER BY s.id DESC LIMIT ?",
        (limit,)).fetchall()
    for s in pending:
        body = json.loads(s["body"])
        vdir = ROOT / cfg["paths"]["queue"] / f"s{s['id']}"
        try:
            meta = voice.synth(body["hook"], body["lines"],
                               cfg["voice"]["primary"], vdir,
                               rate=cfg["voice"].get("rate", "+0%"))
            prod = body.get("product") or {}
            shots = broll.resolve(body.get("shots", []), cfg,
                                  product_media=prod.get("media"),
                                  product_name=prod.get("name"))
            template = ("broll" if any(sh.get("file") for sh in shots)
                        else "clean-card")
            mp4 = render.render(meta, vdir, body=body, shots=shots)
            conn.execute(
                "INSERT INTO videos (script_id, template, file, status, created_at) "
                "VALUES (?,?,?,?,?)",
                (s["id"], template, str(mp4), "rendered", db.now()))
            conn.commit()
            print(f"[produce] script {s['id']} → {mp4} "
                  f"({meta['duration']}s, {template})")
        except Exception as e:
            print(f"[produce] script {s['id']} FAILED: {e}")

    sent = approve.send_pending(conn, cfg)
    if sent:
        print(f"[approve] sent {sent} video(s) to Telegram")
    approve.poll(conn, cfg)
    posted = publish.process(conn, cfg)
    if posted:
        print(f"[publish] posted {posted} video(s)")
    print(json.dumps(db.counts(conn), indent=2))


if __name__ == "__main__":
    main()
