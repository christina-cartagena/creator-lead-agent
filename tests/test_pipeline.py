import json
import subprocess
import sys
from pathlib import Path

import pytest

from agent import dedupe, drafts, inbox, matcher, tracker

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def conn(tmp_path, monkeypatch):
    monkeypatch.setattr(tracker, "DB_PATH", tmp_path / "t.db")
    tracker.init()
    with tracker.connect() as c:
        tracker.add_past_client(c, brand="Haven Candle Company", handle="@havencandleco",
                                email="partnerships@havencandle.example", last_project="reels")
        yield c


def test_past_client_is_skipped_even_when_spelled_differently(conn):
    tracker.add_prospect(conn, brand="Haven Candle Co.", handle="@haven.candle.co")
    tracker.add_prospect(conn, brand="Glow Theory", handle="@glowtheory.skin", niche="skincare")
    rows = dedupe.screen(conn)
    assert [r["result"] for r in rows] == ["skipped", "clear"]
    assert "past client" in rows[0]["reason"]


def test_duplicate_prospect_is_skipped(conn):
    tracker.add_prospect(conn, brand="Fernway Coffee", handle="@fernwaycoffee")
    tracker.add_prospect(conn, brand="Fernway Coffee Roasters", handle="@fern.way.coffee")
    rows = dedupe.screen(conn)
    assert rows[1]["result"] == "skipped" and "duplicate" in rows[1]["reason"]


def test_matcher_prefers_same_niche():
    prospect = {"brand": "Lumen", "niche": "haircare", "why": "before and after posts do well"}
    item, _, why = matcher.best_match(prospect, matcher.load_portfolio())
    assert item["id"] == "hair-before-after"
    assert "same niche" in why


def _matched(conn):
    pid = tracker.add_prospect(conn, brand="Glow Theory", handle="@glowtheory.skin", niche="skincare")
    matcher.match_all(conn)
    return pid


def test_gate_rejects_low_score_and_lint(conn):
    pid = _matched(conn)
    low = drafts.save_draft(conn, prospect_id=pid, channel="instagram", message="Hi there", critic_score=5)
    assert not low["ok"]
    dash = drafts.save_draft(conn, prospect_id=pid, channel="instagram", message="Hi — there", critic_score=9)
    assert dash["problems"]
    ok = drafts.save_draft(conn, prospect_id=pid, channel="instagram", message="Hi Glow team!", critic_score=8)
    assert ok["ok"]


def test_reply_moves_prospect_to_replied(conn):
    pid = _matched(conn)
    out = drafts.save_draft(conn, prospect_id=pid, channel="instagram", message="Hi Glow team!", critic_score=8)
    drafts.mark_sent(conn, out["outreach_id"])
    msg = {"channel": "instagram", "external_id": "ig:1", "sender": "glowtheory.skin",
           "received_at": "2026-11-09T00:00:00Z", "body": "Love it, what are your rates?"}
    res = inbox.sync(conn, [msg])
    assert res[0]["intent"] == "interested"
    assert inbox.sync(conn, [msg]) == []  # idempotent
    status = conn.execute("SELECT status FROM prospects WHERE id=?", (pid,)).fetchone()[0]
    assert status == "replied"


def run_hook(payload):
    p = subprocess.run([sys.executable, str(ROOT / ".claude/hooks/guard_send.py")],
                       input=json.dumps(payload), capture_output=True, text=True)
    return json.loads(p.stdout)["hookSpecificOutput"]["permissionDecision"] if p.stdout.strip() else "allow"


@pytest.mark.parametrize("tool,inp,expected", [
    ("mcp__gmail__send_email", {"to": "x"}, "deny"),
    ("mcp__claude_ai_Gmail__create_draft", {"to": "x"}, "allow"),
    ("mcp__tracker__save_draft", {}, "allow"),
    ("mcp__tracker__followups_due", {}, "allow"),
    ("mcp__tracker__record_replies", {}, "allow"),
    ("Bash", {"command": "curl -X POST https://graph.facebook.com/v21.0/me/messages"}, "deny"),
    ("mcp__claude-in-chrome__navigate", {"url": "https://www.instagram.com/direct/inbox/"}, "deny"),
    ("WebSearch", {"query": "skincare brands ugc"}, "allow"),
])
def test_guard_send_hook(tool, inp, expected):
    assert run_hook({"tool_name": tool, "tool_input": inp}) == expected
