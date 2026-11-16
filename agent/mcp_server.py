"""The tracker as an MCP server, so Claude can use it as a tool.

Registered in .mcp.json; Claude Code starts it automatically. Notice what is
NOT here: there is no tool to send a message or to mark one as sent. The agent
literally cannot do those things. Only the approval queue can.
"""
from __future__ import annotations

import json
from pathlib import Path

from mcp.server.mcpserver import MCPServer

from . import dedupe, drafts, inbox, matcher, tracker

server = MCPServer(
    name="tracker",
    instructions=(
        "Lead tracker for a UGC creator. Always call check_brand before add_prospect. "
        "save_draft enforces the critic score and lint rules; if it refuses, revise the draft. "
        "There is no send tool: the creator sends from the approval queue."
    ),
)


def _rows(rows) -> list[dict]:
    return [dict(r) for r in rows]


@server.tool()
def pipeline_status() -> dict:
    """Counts of prospects at each pipeline stage, plus drafts waiting for approval."""
    with tracker.connect() as conn:
        return {"funnel": tracker.funnel(conn), "awaiting_approval": len(drafts.pending(conn))}


@server.tool()
def check_brand(brand: str, handle: str = "", email: str = "") -> dict:
    """Has this brand been worked with or contacted before? Call before adding a prospect."""
    cand = {"brand": brand, "handle": handle or None, "email": email or None}
    with tracker.connect() as conn:
        past = conn.execute("SELECT * FROM past_clients").fetchall()
        hit = dedupe.find_conflict(cand, past)
        if hit:
            return {"known": True, "as": "past_client", "record": dict(hit[0]), "reason": hit[1]}
        seen = conn.execute("SELECT * FROM prospects").fetchall()
        hit = dedupe.find_conflict(cand, seen)
        if hit:
            return {"known": True, "as": "prospect", "record": dict(hit[0]), "reason": hit[1]}
    return {"known": False}


@server.tool()
def add_prospect(brand: str, why: str, niche: str, handle: str = "", email: str = "",
                 followers: int = 0, source: str = "") -> dict:
    """Add a brand worth contacting. `why` = the specific reason, citing something real they posted or launched."""
    with tracker.connect() as conn:
        pid = tracker.add_prospect(conn, brand=brand, handle=handle or None, email=email or None,
                                   niche=niche, followers=followers or None, source=source, why=why)
    return {"id": pid}


@server.tool()
def screen_and_match() -> dict:
    """Run the code steps: skip past clients and duplicates, then pick a portfolio piece for each new prospect."""
    with tracker.connect() as conn:
        screened = dedupe.screen(conn)
        matched = matcher.match_all(conn)
    return {"screened": screened, "matched": matched}


@server.tool()
def list_prospects(status: str = "matched") -> list[dict]:
    """Prospects at one stage (new, skipped, matched, drafted, sent, replied, won, lost)."""
    with tracker.connect() as conn:
        return _rows(conn.execute("SELECT * FROM prospects WHERE status = ? ORDER BY id", (status,)))


@server.tool()
def get_portfolio_item(item_id: str) -> dict:
    """Full details of one portfolio piece (title, link, result, what it shows)."""
    for it in matcher.load_portfolio():
        if it["id"] == item_id:
            return it
    return {"error": f"no item {item_id}"}


@server.tool()
def save_draft(prospect_id: int, channel: str, message: str, critic_score: int,
               critic_notes: str = "", kind: str = "first_touch") -> dict:
    """Queue a draft for the creator's approval. channel = instagram | email. kind = first_touch | follow_up | reply.
    Refused if critic_score < 7 or the message breaks the lint rules."""
    with tracker.connect() as conn:
        return drafts.save_draft(conn, prospect_id=prospect_id, channel=channel, message=message,
                                 critic_score=critic_score, critic_notes=critic_notes, kind=kind)


@server.tool()
def record_replies(messages_json: str) -> list[dict]:
    """Attach inbox messages to prospects. messages_json = JSON list of
    {channel: email|instagram, external_id, sender, received_at, body}."""
    with tracker.connect() as conn:
        return inbox.sync(conn, json.loads(messages_json))


@server.tool()
def conversation(prospect_id: int) -> dict:
    """Everything sent to and received from one prospect, oldest first."""
    with tracker.connect() as conn:
        p = conn.execute("SELECT * FROM prospects WHERE id = ?", (prospect_id,)).fetchone()
        sent = _rows(conn.execute("SELECT * FROM outreach WHERE prospect_id = ? ORDER BY id", (prospect_id,)))
        got = _rows(conn.execute("SELECT * FROM replies WHERE prospect_id = ? ORDER BY received_at", (prospect_id,)))
    return {"prospect": dict(p) if p else None, "sent": sent, "received": got}


@server.tool()
def followups_due(days: int = 5) -> list[dict]:
    """Prospects who were messaged at least `days` days ago and have not replied."""
    with tracker.connect() as conn:
        return inbox.due_followups(conn, days)


def main() -> None:
    tracker.init()
    server.run("stdio")


if __name__ == "__main__":
    main()
