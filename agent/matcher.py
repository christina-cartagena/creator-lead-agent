"""Pick the one portfolio piece most likely to make *this* brand say yes.

Deterministic on purpose: the score is explainable, and Claude can overrule it
in the pick-portfolio-piece skill when it sees something the tags miss.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from . import tracker

PORTFOLIO_PATH = tracker.ROOT / "config" / "portfolio.json"


def load_portfolio(path: Path | None = None) -> list[dict]:
    p = Path(path or PORTFOLIO_PATH)
    if not p.exists():
        p = tracker.ROOT / "config" / "portfolio.example.json"
    return json.loads(p.read_text(encoding="utf-8"))["items"]


def words(text: str | None) -> set[str]:
    return set(re.findall(r"[a-z]+", (text or "").lower()))


def score(prospect, item: dict) -> tuple[float, str]:
    niche = (prospect["niche"] or "").lower()
    about = words(prospect["why"]) | words(prospect["niche"]) | words(prospect["brand"])
    tags = {t.lower() for t in item["tags"]}
    reasons, s = [], 0.0
    if niche and niche == item["niche"].lower():
        s += 3
        reasons.append(f"same niche ({item['niche']})")
    overlap = about & tags
    if overlap:
        s += 1.5 * len(overlap)
        reasons.append("matches " + ", ".join(sorted(overlap)))
    if item.get("result"):
        s += 0.5
        reasons.append(f"has a result: {item['result']}")
    return s, "; ".join(reasons) or "closest general fit"


def best_match(prospect, portfolio: list[dict]) -> tuple[dict, float, str]:
    ranked = sorted(((score(prospect, it), it) for it in portfolio), key=lambda x: -x[0][0])
    (s, why), item = ranked[0]
    return item, s, why


def match_all(conn, actor: str = "matcher") -> list[dict]:
    portfolio = load_portfolio()
    out = []
    for p in conn.execute("SELECT * FROM prospects WHERE status = 'new' ORDER BY id").fetchall():
        item, s, why = best_match(p, portfolio)
        tracker.set_status(conn, p["id"], "matched", actor, portfolio_item=item["id"], match_reason=why)
        out.append({"id": p["id"], "brand": p["brand"], "item": item["id"], "title": item["title"],
                    "score": round(s, 1), "why": why})
    return out
