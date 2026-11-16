"""Reply monitor: watch Gmail and the Instagram inbox, match answers to prospects.

Two sources, one shape. Each source yields dicts of
    {channel, external_id, sender, received_at, body}
and `sync` attaches them to the right prospect and moves it to 'replied'.

Gmail: Claude reads the inbox through a Gmail MCP connector and passes the
messages in (or you export them to JSON). Instagram: the official Graph API
conversations endpoint, which works for Business and Creator accounts.
Both have JSON fixtures under data/sample so the demo runs offline.
"""
from __future__ import annotations

import json
import os
import urllib.parse
import urllib.request
from pathlib import Path

from . import dedupe, tracker

GRAPH = "https://graph.facebook.com/v21.0"

INTENTS = {
    "interested": ["rates", "rate card", "pricing", "love to", "interested", "send over", "let's chat",
                   "call", "budget", "brief", "sounds great", "yes"],
    "not_now": ["not right now", "next quarter", "maybe later", "circle back", "not at the moment"],
    "no": ["not interested", "no thanks", "unsubscribe", "please remove", "we're all set"],
}


def classify(body: str) -> str:
    """Cheap first pass. The check-replies skill has Claude re-read anything ambiguous."""
    text = body.lower()
    for intent in ("no", "not_now", "interested"):
        if any(phrase in text for phrase in INTENTS[intent]):
            return intent
    return "unclear"


def gmail_messages(path: Path) -> list[dict]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    return [
        {"channel": "email", "external_id": "gmail:" + m["id"], "sender": m["from"],
         "received_at": m["date"], "body": m["snippet"]}
        for m in data["messages"]
    ]


def instagram_messages(path: Path | None = None) -> list[dict]:
    """Read IG DMs from a Graph API response (live, or a saved fixture)."""
    if path:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    else:
        token, ig_user = os.environ.get("IG_ACCESS_TOKEN"), os.environ.get("IG_USER_ID")
        if not (token and ig_user):
            raise RuntimeError("Set IG_ACCESS_TOKEN and IG_USER_ID, or pass --ig-file for the demo")
        q = urllib.parse.urlencode({
            "platform": "instagram",
            "fields": "participants,messages{id,from,message,created_time}",
            "access_token": token,
        })
        with urllib.request.urlopen(f"{GRAPH}/{ig_user}/conversations?{q}", timeout=30) as r:
            data = json.load(r)
    me = data.get("me", os.environ.get("IG_USERNAME", "")).lower()
    out = []
    for convo in data["data"]:
        for m in convo["messages"]["data"]:
            sender = m["from"]["username"]
            if sender.lower() == me:
                continue  # our own outgoing DMs
            out.append({"channel": "instagram", "external_id": "ig:" + m["id"], "sender": sender,
                        "received_at": m["created_time"], "body": m["message"]})
    return out


def _find_prospect(conn, msg):
    for p in conn.execute("SELECT * FROM prospects WHERE status IN ('sent','replied')").fetchall():
        if msg["channel"] == "instagram" and dedupe.handle_key(p["handle"]) == dedupe.handle_key(msg["sender"]):
            return p
        if msg["channel"] == "email":
            addr = msg["sender"].split("<")[-1].rstrip(">").strip().lower()
            if p["email"] and (p["email"].lower() == addr or
                               (dedupe.domain_key(p["email"]) and dedupe.domain_key(p["email"]) == dedupe.domain_key(addr))):
                return p
    return None


def sync(conn, messages: list[dict], actor: str = "inbox") -> list[dict]:
    results = []
    for msg in messages:
        if conn.execute("SELECT 1 FROM replies WHERE external_id = ?", (msg["external_id"],)).fetchone():
            continue  # already recorded on an earlier run
        p = _find_prospect(conn, msg)
        if not p:
            results.append({"sender": msg["sender"], "channel": msg["channel"], "matched": None})
            continue
        intent = classify(msg["body"])
        conn.execute(
            "INSERT INTO replies (prospect_id, channel, external_id, received_at, body, intent) VALUES (?,?,?,?,?,?)",
            (p["id"], msg["channel"], msg["external_id"], msg["received_at"], msg["body"], intent),
        )
        new_status = "lost" if intent == "no" else "replied"
        tracker.set_status(conn, p["id"], new_status, actor)
        results.append({"sender": msg["sender"], "channel": msg["channel"], "matched": p["brand"],
                        "id": p["id"], "intent": intent, "body": msg["body"]})
    return results


def due_followups(conn, days: int = 5) -> list[dict]:
    rows = conn.execute(
        """SELECT p.id, p.brand, p.handle, o.channel, o.sent_at,
                  CAST(julianday('now') - julianday(o.sent_at) AS INTEGER) AS days_waiting,
                  (SELECT COUNT(*) FROM outreach o2 WHERE o2.prospect_id = p.id AND o2.sent_at IS NOT NULL) AS touches
           FROM prospects p JOIN outreach o ON o.prospect_id = p.id
           WHERE p.status = 'sent' AND o.sent_at IS NOT NULL
             AND o.id = (SELECT MAX(id) FROM outreach WHERE prospect_id = p.id AND sent_at IS NOT NULL)
             AND julianday('now') - julianday(o.sent_at) >= ?
           ORDER BY o.sent_at""",
        (days,),
    ).fetchall()
    return [dict(r) for r in rows]
