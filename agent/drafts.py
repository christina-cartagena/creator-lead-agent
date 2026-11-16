"""Drafts: where Claude's messages land, and the gate that decides what reaches the queue.

Claude writes the message (write-dm skill), the dm-critic subagent scores it,
and save_draft refuses anything under the bar. A human is the only one who can
mark a draft as sent, from the approval queue.
"""
from __future__ import annotations

import re

from . import tracker

MIN_SCORE = 7
MAX_WORDS = {"instagram": 90, "email": 160}
BANNED = ["—", "i hope this finds you well", "synergy", "circle back", "quick question",
          "just following up", "dear sir"]


def lint(message: str, channel: str) -> list[str]:
    """Hard rules checked in code, so they hold even when a model forgets them."""
    problems = []
    n = len(re.findall(r"\S+", message))
    if n > MAX_WORDS[channel]:
        problems.append(f"{n} words; limit for {channel} is {MAX_WORDS[channel]}")
    low = message.lower()
    for phrase in BANNED:
        if phrase in low:
            problems.append(f"contains banned phrase {phrase!r}")
    if message.count("http") > 1:
        problems.append("more than one link")
    if "{" in message or "[" in message:
        problems.append("looks like an unfilled template placeholder")
    return problems


def save_draft(conn, *, prospect_id: int, channel: str, message: str, critic_score: int,
               critic_notes: str = "", kind: str = "first_touch", actor: str = "agent") -> dict:
    p = conn.execute("SELECT * FROM prospects WHERE id = ?", (prospect_id,)).fetchone()
    if not p:
        return {"ok": False, "error": f"no prospect #{prospect_id}"}
    allowed = {"first_touch": ("matched", "drafted"), "follow_up": ("sent",), "reply": ("replied",)}[kind]
    if p["status"] not in allowed:
        return {"ok": False, "error": f"prospect #{prospect_id} is '{p['status']}', expected {allowed} for a {kind}"}
    problems = lint(message, channel)
    if problems:
        return {"ok": False, "error": "lint failed", "problems": problems}
    if critic_score < MIN_SCORE:
        return {"ok": False, "error": f"critic score {critic_score} is under {MIN_SCORE}; revise and re-score",
                "critic_notes": critic_notes}
    cur = conn.execute(
        """INSERT INTO outreach (prospect_id, channel, kind, portfolio_item, message, critic_score,
                                 critic_notes, created_at) VALUES (?,?,?,?,?,?,?,?)""",
        (prospect_id, channel, kind, p["portfolio_item"], message, critic_score, critic_notes, tracker.now()),
    )
    if kind == "first_touch":
        tracker.set_status(conn, prospect_id, "drafted", actor)
    else:
        tracker.log(conn, actor, f"draft:{kind}", prospect_id)
    return {"ok": True, "outreach_id": cur.lastrowid, "queued_for_approval": True}


def mark_sent(conn, outreach_id: int, actor: str = "human") -> dict:
    """Called only by the approval queue when the creator presses send herself."""
    o = conn.execute("SELECT * FROM outreach WHERE id = ?", (outreach_id,)).fetchone()
    if not o:
        return {"ok": False, "error": "unknown draft"}
    conn.execute("UPDATE outreach SET sent_at = ? WHERE id = ?", (tracker.now(), outreach_id))
    p = conn.execute("SELECT status FROM prospects WHERE id = ?", (o["prospect_id"],)).fetchone()
    if p["status"] in ("drafted", "matched"):
        tracker.set_status(conn, o["prospect_id"], "sent", actor)
    else:
        tracker.log(conn, actor, "sent", o["prospect_id"], {"outreach_id": outreach_id})
    return {"ok": True}


def pending(conn) -> list[dict]:
    rows = conn.execute(
        """SELECT o.*, p.brand, p.handle, p.email, p.niche, p.followers, p.why, p.match_reason, p.status
           FROM outreach o JOIN prospects p ON p.id = o.prospect_id
           WHERE o.sent_at IS NULL ORDER BY o.critic_score DESC, o.id"""
    ).fetchall()
    return [dict(r) for r in rows]
