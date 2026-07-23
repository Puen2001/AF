"""Human-in-the-loop footage curation. Serves a local web page where the operator
picks the best clip per shot from AI-shortlisted candidates (playable previews),
then returns the chosen file per shot to the pipeline. AI does the searching; the
human does the 2-minute visual judgment it can't.
"""
import http.server
import json
import socketserver
import threading
import urllib.parse
import webbrowser
from pathlib import Path

PAGE = """<!doctype html><html><head><meta charset=utf-8>
<meta name=viewport content="width=device-width,initial-scale=1">
<title>Pick footage</title><style>
body{{background:#111;color:#eee;font-family:system-ui;margin:0;padding:16px}}
h2{{font-size:16px;margin:8px 0}}
.shot{{border-bottom:1px solid #333;padding:14px 0}}
.line{{color:#9ad;margin-bottom:8px;font-size:15px}}
.cands{{display:flex;gap:10px;flex-wrap:wrap}}
label{{position:relative;cursor:pointer;border:3px solid transparent;border-radius:8px;overflow:hidden}}
label.sel{{border-color:#4dd3fc}}
video,img{{width:150px;height:266px;object-fit:cover;display:block;background:#000}}
input{{position:absolute;top:6px;left:6px;transform:scale(1.4)}}
.none{{width:150px;height:266px;display:flex;align-items:center;justify-content:center;
background:#222;color:#888;border-radius:8px}}
#go{{position:sticky;bottom:0;width:100%;padding:16px;font-size:18px;background:#4dd3fc;
border:0;color:#012;font-weight:700;border-radius:8px;margin-top:16px;cursor:pointer}}
</style></head><body>
<h2>เลือกฟุตเทจที่ใช่ที่สุดของแต่ละช็อต</h2>
{shots}
<button id=go onclick=submit()>ยืนยัน &amp; สร้างวิดีโอ</button>
<script>
document.querySelectorAll('input').forEach(i=>i.onchange=()=>{{
 document.querySelectorAll('.shot'+i.name.slice(1)+' label').forEach(l=>l.classList.remove('sel'));
 if(i.parentElement.tagName=='LABEL')i.parentElement.classList.add('sel');}});
function submit(){{
 let picks={{}};document.querySelectorAll('input:checked').forEach(i=>picks[i.name]=i.value);
 fetch('/submit',{{method:'POST',body:JSON.stringify(picks)}}).then(()=>{{
  document.body.innerHTML='<h2>บันทึกแล้ว กำลังสร้างวิดีโอ ปิดหน้านี้ได้เลย</h2>';}});}}
</script></body></html>"""


def _shot_html(idx, shot, files):
    cands = ""
    for j, f in enumerate(files):
        ext = Path(f).suffix.lower()
        media = (f'<video src="/clip/{idx}/{j}" muted loop '
                 f'onmouseover="this.play()" onmouseout="this.pause()"></video>'
                 if ext not in (".jpg", ".jpeg", ".png", ".webp")
                 else f'<img src="/clip/{idx}/{j}">')
        checked = "checked" if j == 0 else ""
        cands += (f'<label class="{"sel" if j==0 else ""}">'
                  f'<input type=radio name="s{idx}" value="{j}" {checked}>{media}</label>')
    cands += (f'<label><input type=radio name="s{idx}" value="none">'
              f'<div class=none>ไม่ใช้<br>(gradient)</div></label>')
    line = shot.get("query") or f"shot {idx}"
    return f'<div class="shot shot{idx}"><div class=line>#{idx+1} · {line}</div><div class=cands>{cands}</div></div>'


def curate(shortlist: list[dict], port: int = 8770, open_browser: bool = True) -> list:
    """Serve the pick page; block until submit; return chosen file per shot (or None)."""
    files_map = {i: sh["candidates"] for i, sh in enumerate(shortlist)}
    result = {"picks": None}
    done = threading.Event()
    html = PAGE.format(shots="\n".join(
        _shot_html(i, sh, sh["candidates"]) for i, sh in enumerate(shortlist)))

    class H(http.server.BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def do_GET(self):
            if self.path == "/":
                body = html.encode()
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
            elif self.path.startswith("/clip/"):
                _, _, si, ci = self.path.split("/")
                f = Path(files_map[int(si)][int(ci)])
                data = f.read_bytes()
                self.send_response(200)
                self.send_header("Content-Type", "video/mp4" if f.suffix.lower()
                                 not in (".jpg", ".jpeg", ".png", ".webp") else "image/jpeg")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)
            else:
                self.send_error(404)

        def do_POST(self):
            n = int(self.headers.get("Content-Length", 0))
            picks = json.loads(self.rfile.read(n) or b"{}")
            chosen = []
            for i, sh in enumerate(shortlist):
                v = picks.get(f"s{i}", "0")
                chosen.append(None if v == "none" else sh["candidates"][int(v)])
            result["picks"] = chosen
            self.send_response(200)
            self.end_headers()
            done.set()

    srv = socketserver.TCPServer(("127.0.0.1", port), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    url = f"http://127.0.0.1:{port}/"
    print(f"[curate] open {url} to pick footage")
    if open_browser:
        try:
            webbrowser.open(url)
        except Exception:
            pass
    done.wait()
    srv.shutdown()
    return result["picks"] or [None] * len(shortlist)
