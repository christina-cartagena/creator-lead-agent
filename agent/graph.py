"""The workflow as a graph: nodes are steps, edges are handoffs, gates are checks.

Some nodes are plain code (screen, match, sync). Some are Claude (find, draft,
critic). One is a person (send). Writing it down as data means the daily run,
the docs and the article all describe the same thing.

    python -m agent graph            # print it
    python -m agent graph --mermaid  # paste into any Mermaid renderer
"""
from __future__ import annotations

NODES = [
    # id,          who,      what
    ("find",      "claude", "Find brands that fit (find-prospects skill)"),
    ("screen",    "code",   "Skip past clients and duplicates"),
    ("match",     "code",   "Pick the best portfolio piece"),
    ("draft",     "claude", "Write the DM or email (write-dm skill)"),
    ("critic",    "claude", "Score the draft 1-10 (dm-critic subagent)"),
    ("gate",      "code",   "Lint + score >= 7, else back to draft"),
    ("queue",     "code",   "Approval queue"),
    ("send",      "human",  "Creator presses send"),
    ("monitor",   "code",   "Watch Gmail + IG inbox for replies"),
    ("followup",  "claude", "Draft a follow-up after 5 quiet days"),
    ("respond",   "claude", "Draft a reply to interested brands"),
]

EDGES = [
    ("find", "screen", ""),
    ("screen", "match", "clear"),
    ("match", "draft", ""),
    ("draft", "critic", ""),
    ("critic", "gate", ""),
    ("gate", "draft", "score < 7"),
    ("gate", "queue", "pass"),
    ("queue", "send", ""),
    ("send", "monitor", ""),
    ("monitor", "respond", "replied"),
    ("monitor", "followup", "no reply in 5 days"),
    ("followup", "critic", ""),
    ("respond", "critic", ""),
]


def text() -> str:
    width = max(len(n[0]) for n in NODES)
    lines = ["NODES"]
    lines += [f"  {nid:<{width}}  [{who:^6}]  {what}" for nid, who, what in NODES]
    lines.append("EDGES")
    lines += [f"  {a:<{width}} -> {b:<{width}}  {label}".rstrip() for a, b, label in EDGES]
    return "\n".join(lines)


def mermaid() -> str:
    shape = {"claude": ("([", "])"), "code": ("[", "]"), "human": ("{{", "}}")}
    out = ["flowchart LR"]
    for nid, who, what in NODES:
        l, r = shape[who]
        out.append(f'  {nid}{l}"{what}"{r}')
    for a, b, label in EDGES:
        out.append(f"  {a} -->|{label}| {b}" if label else f"  {a} --> {b}")
    return "\n".join(out)
