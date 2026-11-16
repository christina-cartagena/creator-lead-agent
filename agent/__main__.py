"""Command line for the code-only steps. Claude calls the same logic through MCP.

    python -m agent init --demo        create the database and load sample data
    python -m agent screen             skip past clients and duplicates
    python -m agent match              pick a portfolio piece per prospect
    python -m agent queue              open the approval queue (localhost:8765)
    python -m agent sync --demo        pull replies from Gmail + IG fixtures
    python -m agent followups          who is due a follow-up
    python -m agent status             the funnel
    python -m agent graph [--mermaid]  print the workflow graph
"""
from __future__ import annotations

import argparse
import csv
import json
import sys

from . import dedupe, graph, inbox, matcher, queue_app, tracker

SAMPLE = tracker.ROOT / "data" / "sample"


def load_csv(path):
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def cmd_init(args):
    if args.demo and tracker.DB_PATH.exists():
        tracker.DB_PATH.unlink()
    tracker.init()
    if not args.demo:
        print(f"Created {tracker.DB_PATH.relative_to(tracker.ROOT)}")
        return
    with tracker.connect() as conn:
        for r in load_csv(SAMPLE / "past_clients.csv"):
            tracker.add_past_client(conn, **r)
        for r in load_csv(SAMPLE / "prospects.csv"):
            r["followers"] = int(r["followers"]) if r["followers"] else None
            tracker.add_prospect(conn, actor="seed", **{k: (v or None) for k, v in r.items()})
        n_past = conn.execute("SELECT COUNT(*) FROM past_clients").fetchone()[0]
        n_new = conn.execute("SELECT COUNT(*) FROM prospects").fetchone()[0]
    print(f"Demo data loaded: {n_past} past clients, {n_new} new prospects (all fictional)")


def cmd_screen(args):
    with tracker.connect() as conn:
        rows = dedupe.screen(conn)
    for r in rows:
        mark = "SKIP " if r["result"] == "skipped" else "clear"
        print(f"  {mark}  #{r['id']:<3} {r['brand']:<26} {r['reason']}")
    skipped = sum(r["result"] == "skipped" for r in rows)
    print(f"\n{len(rows)} screened, {skipped} skipped, {len(rows) - skipped} clear to pitch")


def cmd_match(args):
    with tracker.connect() as conn:
        rows = matcher.match_all(conn)
    for r in rows:
        print(f"  #{r['id']:<3} {r['brand']:<26} -> {r['title']:<36} ({r['why']})")
    print(f"\n{len(rows)} prospects matched to a portfolio piece")


def cmd_sync(args):
    msgs = []
    if args.demo or args.gmail_file:
        msgs += inbox.gmail_messages(args.gmail_file or SAMPLE / "gmail_inbox.json")
    if args.demo or args.ig_file or args.live_ig:
        msgs += inbox.instagram_messages(None if args.live_ig else (args.ig_file or SAMPLE / "ig_conversations.json"))
    with tracker.connect() as conn:
        rows = inbox.sync(conn, msgs)
    for r in rows:
        if r["matched"]:
            print(f"  {r['channel']:<9} {r['matched']:<24} {r['intent']:<11} \"{r['body'][:60]}\"")
        else:
            print(f"  {r['channel']:<9} {r['sender']:<24} (not a prospect, ignored)")
    print(f"\n{sum(1 for r in rows if r['matched'])} new replies recorded")


def cmd_followups(args):
    with tracker.connect() as conn:
        rows = inbox.due_followups(conn, args.days)
    for r in rows:
        print(f"  #{r['id']:<3} {r['brand']:<26} {r['channel']:<9} waiting {r['days_waiting']} days, {r['touches']} touch(es)")
    print(f"\n{len(rows)} due a follow-up")


def cmd_status(args):
    with tracker.connect() as conn:
        counts = tracker.funnel(conn)
    top = max(counts.values()) or 1
    for s, n in counts.items():
        print(f"  {s:<8} {n:>3}  {'#' * round(24 * n / top)}")


def cmd_graph(args):
    print(graph.mermaid() if args.mermaid else graph.text())


def main(argv=None):
    ap = argparse.ArgumentParser(prog="python -m agent", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("init"); p.add_argument("--demo", action="store_true"); p.set_defaults(fn=cmd_init)
    sub.add_parser("screen").set_defaults(fn=cmd_screen)
    sub.add_parser("match").set_defaults(fn=cmd_match)
    p = sub.add_parser("queue"); p.add_argument("--port", type=int, default=8765)
    p.set_defaults(fn=lambda a: queue_app.serve(a.port))
    p = sub.add_parser("sync"); p.add_argument("--demo", action="store_true")
    p.add_argument("--gmail-file"); p.add_argument("--ig-file"); p.add_argument("--live-ig", action="store_true")
    p.set_defaults(fn=cmd_sync)
    p = sub.add_parser("followups"); p.add_argument("--days", type=int, default=5); p.set_defaults(fn=cmd_followups)
    sub.add_parser("status").set_defaults(fn=cmd_status)
    p = sub.add_parser("graph"); p.add_argument("--mermaid", action="store_true"); p.set_defaults(fn=cmd_graph)
    args = ap.parse_args(argv)
    args.fn(args)


if __name__ == "__main__":
    sys.exit(main())
