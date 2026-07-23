"""Stage 5 — human approval gate via Telegram. This is the operator's ENTIRE
recurring job: one ✅/❌ tap per video.

send_pending(): rendered videos → Telegram (video + hook + marketing preview +
inline buttons) → status pending_approval.
poll(): getUpdates callbacks → approved/rejected; offset persisted in kv.
Without TELEGRAM_BOT_TOKEN both are graceful no-ops that say what's waiting.
"""
import json
import os

import requests

from . import db


def _tg(token: str, method: str, *, files=None, **params):
    r = requests.post(f"https://api.telegram.org/bot{token}/{method}",
                      data=params, files=files, timeout=120)
    r.raise_for_status()
    return r.json()["result"]


def _env():
    return os.environ.get("TELEGRAM_BOT_TOKEN"), os.environ.get("TELEGRAM_CHAT_ID")


def send_pending(conn, cfg) -> int:
    token, chat = _env()
    rendered = db.rows(conn, "videos", "rendered")
    if not rendered:
        return 0
    if not token or not chat:
        print(f"[approve] no TELEGRAM_BOT_TOKEN/CHAT_ID — "
              f"{len(rendered)} video(s) waiting in queue/")
        return 0
    sent = 0
    for v in rendered:
        s = conn.execute("SELECT * FROM scripts WHERE id=?",
                         (v["script_id"],)).fetchone()
        p = conn.execute("SELECT * FROM products WHERE id=?",
                         (s["product_id"],)).fetchone()
        body = json.loads(s["body"])
        yt = body.get("marketing", {}).get("youtube", {})
        caption = (f"🎬 {p['name']}\n"
                   f"「{body['hook']}」\n\n"
                   f"YT: {yt.get('title', '-')}\n"
                   f"✅ = โพสต์  |  ❌ = ทิ้ง")
        kb = {"inline_keyboard": [[
            {"text": "✅ โพสต์", "callback_data": f"ok:{v['id']}"},
            {"text": "❌ ทิ้ง", "callback_data": f"no:{v['id']}"}]]}
        with open(v["file"], "rb") as f:
            msg = _tg(token, "sendVideo", chat_id=chat, caption=caption[:1024],
                      reply_markup=json.dumps(kb), files={"video": f})
        conn.execute("UPDATE videos SET status='pending_approval', tg_msg_id=? "
                     "WHERE id=?", (msg["message_id"], v["id"]))
        conn.commit()
        sent += 1
    return sent


def poll(conn, cfg) -> int:
    token, chat = _env()
    if not token:
        return 0
    offset = int(db.kv_get(conn, "tg_offset", "0"))
    updates = _tg(token, "getUpdates", offset=offset + 1, timeout=0)
    handled = 0
    for u in updates:
        db.kv_set(conn, "tg_offset", str(u["update_id"]))
        cb = u.get("callback_query")
        if not cb or ":" not in (cb.get("data") or ""):
            continue
        # getUpdates is bot-wide: only the owner chat may flip approval state
        sender = cb.get("from", {}).get("id")
        cb_chat = cb.get("message", {}).get("chat", {}).get("id")
        if str(sender) != str(chat) or str(cb_chat) != str(chat):
            _tg(token, "answerCallbackQuery", callback_query_id=cb["id"],
                text="ไม่ได้รับอนุญาต")
            continue
        action, vid = cb["data"].split(":", 1)
        try:
            vid = int(vid)
        except ValueError:
            _tg(token, "answerCallbackQuery", callback_query_id=cb["id"])
            continue
        v = conn.execute("SELECT * FROM videos WHERE id=?", (vid,)).fetchone()
        if not v or v["status"] != "pending_approval":
            _tg(token, "answerCallbackQuery", callback_query_id=cb["id"])
            continue
        status = "approved" if action == "ok" else "rejected"
        db.set_status(conn, "videos", v["id"], status)
        _tg(token, "answerCallbackQuery", callback_query_id=cb["id"],
            text="อนุมัติแล้ว กำลังโพสต์" if action == "ok" else "ทิ้งแล้ว")
        if v["tg_msg_id"]:
            try:
                _tg(token, "editMessageCaption", chat_id=chat,
                    message_id=v["tg_msg_id"],
                    caption=("✅ อนุมัติแล้ว — กำลังโพสต์"
                             if action == "ok" else "❌ ทิ้งแล้ว"))
            except Exception:
                pass
        handled += 1
    return handled


def notify(text: str):
    token, chat = _env()
    if token and chat:
        try:
            _tg(token, "sendMessage", chat_id=chat, text=text[:4096])
        except Exception:
            pass
