"""Mine the niche for OUTLIER shorts — videos pulling big views off small channels,
which means the CONTENT is winning (a proven, replicable topic/hook), not the
channel's existing audience. Feeds proven topics into trend discovery.

Legit use: learn what topic/angle is already working → make our OWN original story
on it. We do NOT download or re-upload anyone's footage (that's copyright).
Keyless via yt-dlp (YouTube metadata only, no API key).
"""
import json
import os
import subprocess

import requests

MIN_VIEWS = 15_000      # floor for "has traction"
MAX_DUR = 90            # shorts only
SUBS_FLOOR = 3_000      # avoid divide-by-tiny; also the "small channel" reference


def _api_search(query: str, key: str, n: int) -> list[dict]:
    """YouTube Data API — order by viewCount to actually surface top performers
    (what the keyless yt-dlp path can't do). ~100 quota units/query."""
    try:
        s = requests.get("https://www.googleapis.com/youtube/v3/search", params={
            "key": key, "q": query, "part": "snippet", "type": "video",
            "videoDuration": "short", "order": "viewCount", "maxResults": n,
            "regionCode": "TH", "relevanceLanguage": "th"}, timeout=30)
        s.raise_for_status()
        ids = [it["id"]["videoId"] for it in s.json().get("items", [])
               if it.get("id", {}).get("videoId")]
        if not ids:
            return []
        v = requests.get("https://www.googleapis.com/youtube/v3/videos", params={
            "key": key, "id": ",".join(ids),
            "part": "statistics,snippet,contentDetails"}, timeout=30)
        v.raise_for_status()
        items = v.json().get("items", [])
        # channel subs in one batch
        chans = list({it["snippet"]["channelId"] for it in items})
        c = requests.get("https://www.googleapis.com/youtube/v3/channels", params={
            "key": key, "id": ",".join(chans), "part": "statistics"}, timeout=30)
        subs = {ch["id"]: int(ch["statistics"].get("subscriberCount", 0))
                for ch in c.json().get("items", [])}
        out = []
        for it in items:
            dur = _iso_dur(it["contentDetails"]["duration"])
            out.append({"id": it["id"], "title": it["snippet"]["title"],
                        "view_count": int(it["statistics"].get("viewCount", 0)),
                        "channel_follower_count": subs.get(it["snippet"]["channelId"], 0),
                        "channel": it["snippet"]["channelTitle"], "duration": dur})
        return out
    except Exception:
        return []


def _iso_dur(iso: str) -> int:
    import re
    m = re.match(r"PT(?:(\d+)M)?(?:(\d+)S)?", iso or "")
    return (int(m.group(1) or 0) * 60 + int(m.group(2) or 0)) if m else 999


def _search(query: str, n: int) -> list[dict]:
    try:
        out = subprocess.run(
            ["yt-dlp", f"ytsearch{n}:{query}", "-j", "--no-warnings",
             "--socket-timeout", "20"],
            capture_output=True, text=True, timeout=180)
    except Exception:
        return []
    vids = []
    for line in out.stdout.splitlines():
        try:
            vids.append(json.loads(line))
        except Exception:
            continue
    return vids


def mine(queries: list[str], per: int = 12, top: int = 10) -> list[dict]:
    """Return the top outlier shorts across the niche queries, ranked by how much
    they over-perform their channel size (views / subscribers). Uses the YouTube
    Data API (order=viewCount) when YOUTUBE_API_KEY is set — the proper way to
    surface outliers — else falls back to keyless yt-dlp (weaker: relevance-ordered)."""
    key = os.environ.get("YOUTUBE_API_KEY")
    fetch = (lambda q, n: _api_search(q, key, n)) if key else _search
    seen, winners = set(), []
    for q in queries:
        for v in fetch(q, per):
            vid = v.get("id")
            dur = v.get("duration") or 999
            views = v.get("view_count") or 0
            subs = v.get("channel_follower_count") or 0
            if not vid or vid in seen or dur > MAX_DUR or views < MIN_VIEWS:
                continue
            seen.add(vid)
            ratio = round(views / max(subs, SUBS_FLOOR), 2)
            winners.append({"title": v.get("title", ""), "views": views,
                            "subs": subs, "ratio": ratio,
                            "channel": v.get("channel", "")})
    # outlier = high over-performance vs channel size
    winners.sort(key=lambda w: w["ratio"], reverse=True)
    return winners[:top]


def as_signal(winners: list[dict]) -> str:
    """Compact text block for the discovery prompt."""
    if not winners:
        return "ไม่มีข้อมูล outlier"
    return "\n".join(
        f"- \"{w['title'][:70]}\" ({w['views']:,} views / {w['subs']:,} subs, x{w['ratio']})"
        for w in winners)
