"""Stage 6 — publish approved videos.

YouTube: official Data API upload (OAuth). First auth is interactive
(`python run.py yt-auth` on a machine with a browser); after that the token
refreshes headlessly. TikTok: no auto-post (API is private-only pre-audit) —
the operator gets a ready-to-paste caption via Telegram; the video file is
already on their phone from the approval message.
"""
import json
import os
import sys
from pathlib import Path

from . import approve, db

ROOT = Path(__file__).resolve().parent.parent
TOKEN_FILE = ROOT / "config" / "yt_token.json"
SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]


def yt_creds(interactive: bool = False):
    try:
        from google.auth.transport.requests import Request
        from google.oauth2.credentials import Credentials
    except ImportError:
        print("[publish] google-api-python-client not installed")
        return None
    creds = None
    if TOKEN_FILE.exists():
        creds = Credentials.from_authorized_user_file(str(TOKEN_FILE), SCOPES)
    if creds and creds.expired and creds.refresh_token:
        try:
            creds.refresh(Request())
            TOKEN_FILE.write_text(creds.to_json())
        except Exception as e:
            print(f"[publish] token refresh failed ({e}) — rerun: python run.py yt-auth")
            return None
    if creds and creds.valid:
        return creds
    secret = os.environ.get("YOUTUBE_CLIENT_SECRET_JSON")
    if not secret or not Path(secret).exists():
        print("[publish] no YouTube credentials — set YOUTUBE_CLIENT_SECRET_JSON "
              "in secrets.env, then: python run.py yt-auth")
        return None
    if not (interactive and sys.stdout.isatty()):
        print("[publish] YouTube auth needed — run: python run.py yt-auth")
        return None
    from google_auth_oauthlib.flow import InstalledAppFlow
    flow = InstalledAppFlow.from_client_secrets_file(secret, SCOPES)
    creds = flow.run_local_server(port=0)
    TOKEN_FILE.write_text(creds.to_json())
    return creds


def _upload_youtube(creds, video, body, cfg, affiliate_link) -> str:
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaFileUpload
    yt = build("youtube", "v3", credentials=creds)
    mkt = body.get("marketing", {}).get("youtube", {})
    title = (mkt.get("title") or body["hook"])[:95]
    desc = mkt.get("description") or body.get("caption", "")
    if affiliate_link:
        desc = f"สนใจดูสินค้า: {affiliate_link}\n\n{desc}"
    pub = cfg.get("publish", {})
    req = yt.videos().insert(
        part="snippet,status",
        body={"snippet": {"title": title, "description": desc,
                          "categoryId": pub.get("category_id", "28")},
              "status": {"privacyStatus": pub.get("privacy", "unlisted"),
                         "selfDeclaredMadeForKids": False}},
        media_body=MediaFileUpload(video["file"], chunksize=-1, resumable=True))
    resp = req.execute()
    return f"https://youtube.com/shorts/{resp['id']}"


def process(conn, cfg) -> int:
    approved = db.rows(conn, "videos", "approved")
    if not approved:
        return 0
    creds = yt_creds()
    done = 0
    for v in approved:
        s = conn.execute("SELECT * FROM scripts WHERE id=?",
                         (v["script_id"],)).fetchone()
        p = (conn.execute("SELECT * FROM products WHERE id=?",
                          (s["product_id"],)).fetchone()
             if s["product_id"] else None)          # topic-mode scripts have no product
        affiliate_link = p["affiliate_link"] if p else None
        body = json.loads(s["body"])

        url = None
        if creds:
            try:
                url = _upload_youtube(creds, v, body, cfg, affiliate_link)
                conn.execute(
                    "INSERT INTO posts (video_id, platform, url, posted_at) "
                    "VALUES (?,?,?,?)", (v["id"], "youtube", url, db.now()))
                conn.commit()
            except Exception as e:
                print(f"[publish] youtube upload failed for video {v['id']}: {e}")

        # TikTok hand-off: ready-to-paste caption (video already on the phone)
        tt = body.get("marketing", {}).get("tiktok", {})
        tt_caption = (tt.get("caption") or body.get("caption", ""))
        if tt.get("hashtags"):
            tt_caption += "\n" + " ".join(tt["hashtags"])
        if affiliate_link:
            tt_caption += f"\nลิงก์สินค้า: {affiliate_link}"
        approve.notify(
            (f"🚀 โพสต์ YouTube แล้ว: {url}\n\n" if url else "")
            + f"📋 TikTok — ก๊อปแคปชันนี้ไปโพสต์คู่กับวิดีโอด้านบน:\n\n{tt_caption}")

        if url:
            db.set_status(conn, "videos", v["id"], "posted")
            done += 1
        # no YouTube creds yet → stays 'approved', retried next poll/daily run
    return done
