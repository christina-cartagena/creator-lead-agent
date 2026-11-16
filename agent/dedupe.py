"""Screening: never pitch a brand twice, and never cold-pitch a past client.

Brands show up spelled many ways ("Haven Candle Co.", "@haven.candle.co",
"hello@havencandle.example"), so we compare normalized keys instead of raw strings.
"""
from __future__ import annotations

import re
from difflib import SequenceMatcher

SUFFIXES = r"\b(co|company|inc|llc|ltd|brand|brands|shop|store|official|the|hq)\b"
FREE_MAIL = {"gmail.com", "yahoo.com", "outlook.com", "hotmail.com", "icloud.com", "aol.com"}


def brand_key(name: str | None) -> str:
    if not name:
        return ""
    s = name.lower().replace("&", " and ")
    s = re.sub(r"[^a-z0-9 ]+", " ", s)
    s = re.sub(SUFFIXES, " ", s)
    return re.sub(r"\s+", "", s)


def handle_key(handle: str | None) -> str:
    if not handle:
        return ""
    s = handle.strip().lower().lstrip("@")
    s = re.sub(r"^(https?://)?(www\.)?instagram\.com/", "", s).strip("/")
    s = re.sub(r"[._]", "", s)
    return re.sub(r"(company|official|shop|store|hq|co)$", "", s) or s


def domain_key(email: str | None) -> str:
    if not email or "@" not in email:
        return ""
    domain = email.split("@", 1)[1].lower().strip()
    return "" if domain in FREE_MAIL else brand_key(domain.rsplit(".", 1)[0])


def keys(record) -> set[str]:
    out = {
        "b:" + brand_key(record["brand"]),
        "h:" + handle_key(record["handle"]),
        "d:" + domain_key(record["email"]),
    }
    return {k for k in out if len(k) > 4}


def similar(a: str, b: str) -> float:
    return SequenceMatcher(None, a, b).ratio()


def find_conflict(candidate, others, threshold: float = 0.88):
    """Return (other_record, reason) if candidate collides with any of others, else None."""
    cand_keys = keys(candidate)
    cand_brand = brand_key(candidate["brand"])
    for other in others:
        shared = cand_keys & keys(other)
        if shared:
            kind = {"b": "same brand", "h": "same Instagram handle", "d": "same email domain"}
            return other, kind[sorted(shared)[0][0]]
        other_brand = brand_key(other["brand"])
        if cand_brand and other_brand and similar(cand_brand, other_brand) >= threshold:
            return other, f"brand name {similar(cand_brand, other_brand):.0%} similar"
    return None


def screen(conn, actor: str = "screen") -> list[dict]:
    """Screen every 'new' prospect. Returns one result row per prospect."""
    from . import tracker

    past = conn.execute("SELECT * FROM past_clients").fetchall()
    results = []
    for p in conn.execute("SELECT * FROM prospects WHERE status = 'new' ORDER BY id").fetchall():
        hit = find_conflict(p, past)
        if hit:
            other, reason = hit
            msg = f"past client {other['brand']} ({reason}; last project: {other['last_project']})"
            tracker.set_status(conn, p["id"], "skipped", actor, skip_reason=msg)
            results.append({"id": p["id"], "brand": p["brand"], "result": "skipped", "reason": msg})
            continue
        earlier = conn.execute(
            "SELECT * FROM prospects WHERE id != ? AND status != 'skipped' AND id < ?", (p["id"], p["id"])
        ).fetchall()
        hit = find_conflict(p, earlier)
        if hit:
            other, reason = hit
            msg = f"duplicate of #{other['id']} {other['brand']} ({reason}, status {other['status']})"
            tracker.set_status(conn, p["id"], "skipped", actor, skip_reason=msg)
            results.append({"id": p["id"], "brand": p["brand"], "result": "skipped", "reason": msg})
            continue
        results.append({"id": p["id"], "brand": p["brand"], "result": "clear", "reason": ""})
    return results
