"""The approval queue: the one screen where a human presses send.

    python -m agent queue        -> http://localhost:8765

Each card shows who the brand is, why the agent picked them, which portfolio
piece it chose, the draft, and the critic's score. "Copy & open" puts the
message on the clipboard and opens the brand's Instagram (or a prefilled email).
Sending happens in Instagram or Gmail, by hand. "I sent it" records that.
"""
from __future__ import annotations

import html
import json
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from . import drafts, matcher, tracker

PAGE = """<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Approval queue</title><style>
:root{--bg:#f7f5f2;--card:#fff;--ink:#1d1b19;--quiet:#6b655e;--line:#e6e1da;--accent:#c2410c;--good:#15803d}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:15px/1.5 system-ui,-apple-system,Segoe UI,sans-serif}
header{padding:28px 32px 8px;max-width:980px;margin:auto}h1{margin:0;font-size:24px}header p{margin:4px 0 0;color:var(--quiet)}
.funnel{display:flex;gap:8px;flex-wrap:wrap;margin:16px 0 0}.funnel span{background:var(--card);border:1px solid var(--line);border-radius:999px;padding:4px 12px;font-size:13px}
.funnel b{font-variant-numeric:tabular-nums}main{max-width:980px;margin:auto;padding:16px 32px 48px;display:grid;gap:16px}
.card{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:20px 22px;display:grid;grid-template-columns:1fr 1.25fr;gap:20px}
.brand{font-weight:650;font-size:17px}.meta{color:var(--quiet);font-size:13px}.why{margin:10px 0 0;font-size:14px}
.pill{display:inline-block;font-size:12px;border-radius:6px;padding:2px 8px;background:#fff1e8;color:var(--accent);margin-right:6px}
.piece{margin-top:12px;padding:10px 12px;border:1px dashed var(--line);border-radius:10px;font-size:13px}
.msg{white-space:pre-wrap;font-family:inherit;line-height:1.55;background:#faf9f7;border:1px solid var(--line);border-radius:10px;padding:12px 14px;font-size:14px;margin:0}
.score{font-size:13px;color:var(--good);font-weight:600;margin:0 0 8px}.notes{font-size:12.5px;color:var(--quiet);margin:8px 0 0}
.actions{display:flex;gap:8px;margin-top:12px;flex-wrap:wrap}button,a.btn{font:inherit;font-size:14px;border-radius:9px;padding:8px 14px;cursor:pointer;border:1px solid var(--line);background:#fff;color:var(--ink);text-decoration:none}
.primary{background:var(--ink)!important;color:#fff!important;border-color:var(--ink)!important}.done{opacity:.45}
.empty{color:var(--quiet);text-align:center;padding:60px 0}@media(max-width:760px){.card{grid-template-columns:1fr}header,main{padding-left:16px;padding-right:16px}}
</style></head><body><header><h1>Approval queue</h1>
<p>The agent drafts. You decide. Nothing leaves without you pressing send.</p><div class="funnel">%FUNNEL%</div></header>
<main>%CARDS%</main><script>
async function post(path, id){await fetch(path,{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({id})});}
async function copyOpen(btn){const c=btn.closest('.card');await navigator.clipboard.writeText(c.querySelector('.msg').innerText);window.open(btn.dataset.url,'_blank');btn.textContent='Copied';}
async function sent(btn){await post('/api/sent',+btn.dataset.id);btn.closest('.card').classList.add('done');btn.textContent='Marked sent';}
</script></body></html>"""


def _card(d: dict, items: dict) -> str:
    e = html.escape
    item = items.get(d["portfolio_item"] or "", {})
    if d["channel"] == "instagram":
        url = f"https://www.instagram.com/{(d['handle'] or '').lstrip('@')}/"
        where, label = f"Instagram {e(d['handle'] or '')}", "Copy &amp; open Instagram"
    else:
        subject = f"UGC for {d['brand']}"
        url = "mailto:" + (d["email"] or "") + "?" + urllib.parse.urlencode(
            {"subject": subject, "body": d["message"]}, quote_via=urllib.parse.quote)
        where, label = f"Email {e(d['email'] or '')}", "Copy &amp; open email"
    kind = {"first_touch": "first touch", "follow_up": "follow-up", "reply": "reply"}[d["kind"]]
    followers = f"{d['followers']:,} followers" if d["followers"] else ""
    return f"""<section class="card"><div>
<div class="brand">{e(d['brand'])}</div><div class="meta">{where} &middot; {e(d['niche'] or '')} &middot; {followers}</div>
<p class="why"><span class="pill">{kind}</span>{e(d['why'] or '')}</p>
<div class="piece"><b>Portfolio pick:</b> {e(item.get('title', d['portfolio_item'] or ''))}<br>
<span class="meta">{e(d['match_reason'] or '')}</span></div></div>
<div><p class="score">Critic score {d['critic_score']}/10</p><pre class="msg">{e(d['message'])}</pre>
<p class="notes">{e(d['critic_notes'] or '')}</p>
<div class="actions"><button class="primary" data-url="{e(url)}" onclick="copyOpen(this)">{label}</button>
<button data-id="{d['id']}" onclick="sent(this)">I sent it</button></div></div></section>"""


def render() -> str:
    items = {it["id"]: it for it in matcher.load_portfolio()}
    with tracker.connect() as conn:
        rows = drafts.pending(conn)
        counts = tracker.funnel(conn)
    funnel = "".join(f"<span>{s} <b>{n}</b></span>" for s, n in counts.items())
    cards = "".join(_card(d, items) for d in rows) or '<p class="empty">Queue is empty. The agent will add drafts on its next run.</p>'
    return PAGE.replace("%FUNNEL%", funnel).replace("%CARDS%", cards)


class Handler(BaseHTTPRequestHandler):
    def _send(self, code: int, body: str, ctype: str = "text/html; charset=utf-8"):
        data = body.encode("utf-8")
        self.send_response(code)
        self.send_header("content-type", ctype)
        self.send_header("content-length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        if self.path in ("/", "/index.html"):
            self._send(200, render())
        else:
            self._send(404, "not found", "text/plain")

    def do_POST(self):
        if self.path != "/api/sent":
            return self._send(404, "not found", "text/plain")
        length = int(self.headers.get("content-length", 0))
        payload = json.loads(self.rfile.read(length) or b"{}")
        with tracker.connect() as conn:
            result = drafts.mark_sent(conn, int(payload["id"]), actor="human")
        self._send(200, json.dumps(result), "application/json")

    def log_message(self, *args):
        pass


def serve(port: int = 8765) -> None:
    # Bound to localhost only: the queue is for the creator, on her own machine.
    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    print(f"Approval queue running at http://localhost:{port}  (Ctrl+C to stop)")
    server.serve_forever()
