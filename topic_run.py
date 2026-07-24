#!/usr/bin/env python3
"""TOGE-model driver: TOPIC-FIRST clip production.

Trend/topic discovery → FOOTAGE FEASIBILITY GATE (pick a story the footage can tell) →
story ladder → situational product attach (product = natural ending) → muted-test
footage → render. Product is an OUTPUT, never the input. Usage: python topic_run.py
"""
import json
from pathlib import Path

import yaml

from factory import broll, db, render, scriptgen, topics, trends, voice

ROOT = Path(__file__).resolve().parent


def main():
    cfg = yaml.safe_load((ROOT / "config" / "config.yaml").read_text())
    cfg["mode"] = "story-first"                     # this driver is always topic-first
    conn = db.connect()

    print("[topic] Stage 0 — discovering trending story topics (WebSearch)...", flush=True)
    print(f"[topic] {trends.discover(conn, cfg)}", flush=True)
    cands = db.rows(conn, "topics", "discovered", 8, order="audience_fit DESC, id")
    if not cands:
        print("[topic] no candidate topics — stopping", flush=True)
        return
    print(f"[topic] {len(cands)} candidates. Stage 0.5 — FOOTAGE FEASIBILITY SCAN...", flush=True)

    ranked = topics.rank(conn, cfg, cands)
    for r in ranked:
        f = r["feasibility"]
        print(f"[topic] score {r['score']:.2f} | footage {f['score']:.2f} "
              f"({f['searchable']}/{f['total']} beats, core-confirmed={f['confirmed']}) "
              f"| {r['topic']['title'][:55]}", flush=True)
    win = ranked[0]["topic"]
    print(f"[topic] WINNER: {win['title']}  (beats: {ranked[0]['feasibility']['beats']})", flush=True)

    print("[topic] story ladder + situational product match...", flush=True)
    r = scriptgen.generate_from_topic(conn, win, cfg)
    print(f"[topic] script: {json.dumps(r, ensure_ascii=False)[:280]}", flush=True)

    row = conn.execute(
        "SELECT s.* FROM scripts s LEFT JOIN videos v ON v.script_id=s.id "
        "WHERE s.topic_id=? AND s.status='checked' AND v.id IS NULL "
        "ORDER BY s.id DESC LIMIT 1", (win["id"],)).fetchone()
    if not row:
        print("[topic] no checked script produced — stopping", flush=True)
        return
    body = json.loads(row["body"])
    prod = body.get("product") or {}
    pname = prod.get("search") or prod.get("category")     # story-first product = a category
    vdir = ROOT / cfg["paths"]["queue"] / f"s{row['id']}"
    vdir.mkdir(parents=True, exist_ok=True)

    print("[topic] voice...", flush=True)
    meta = voice.synth(body["hook"], body["lines"], cfg["voice"]["primary"], vdir,
                       rate=cfg["voice"].get("rate", "+0%"))
    print(f"[topic] muted-test footage (product-ending={pname!r})...", flush=True)
    shots = broll.resolve(body.get("shots", []), cfg, product_name=pname)
    matched = sum(1 for s in shots if s.get("file"))
    for i, s in enumerate(shots):
        print(f"[topic] shot {i} type={s.get('type')} "
              f"{'VIDEO ' + str(s.get('source')) if s.get('file') else 'CARD (no-match)'} "
              f"{s.get('ref','')}", flush=True)
    print(f"[topic] {matched}/{len(shots)} beats matched real footage", flush=True)

    print("[topic] render...", flush=True)
    mp4 = render.render(meta, vdir, body=body, shots=shots)
    conn.execute("INSERT INTO videos (script_id, template, file, status, created_at) "
                 "VALUES (?,?,?,?,?)", (row["id"], "topic-first", str(mp4),
                                        "rendered", db.now()))
    conn.commit()
    import os
    print(f"[topic] DONE: {mp4} ({os.path.getsize(mp4)//1024}KB) script={row['id']} "
          f"topic={win['id']}", flush=True)


if __name__ == "__main__":
    main()
