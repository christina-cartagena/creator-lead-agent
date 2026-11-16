---
name: check-replies
description: Check Gmail and the Instagram inbox for replies from brands that were contacted, record them in the tracker, and draft the next message. Use when asked about replies, the inbox, who answered, or on the scheduled reply check.
---

# Check replies

## 1. Pull new messages

- **Gmail:** use the Gmail connector to search `newer_than:3d` for messages from any prospect email or domain with status `sent` or `replied` (`mcp__tracker__list_prospects`). Collect `{channel:"email", external_id:"gmail:<id>", sender, received_at, body}`.
- **Instagram:** run `python -m agent sync --live-ig` if `IG_ACCESS_TOKEN` is set (official Graph API conversations endpoint). Otherwise ask the creator to paste any new brand DMs.
- Demo / offline: `python -m agent sync --demo`.

Pass Gmail messages to `mcp__tracker__record_replies` as a JSON list. It matches each one to a prospect, skips anything already recorded, tags intent (interested, not_now, no, unclear) and moves the prospect to `replied` (or `lost` for a clear no).

## 2. Re-read anything unclear
The keyword tagger is a first pass. Read every `unclear` and every `interested` yourself and correct it in your summary.

## 3. Draft the next move (never send)
- **interested:** a reply via the `write-dm` skill, kind `reply`.
- **not_now:** no draft. Note when to come back.
- **no:** nothing. They are marked lost; never contact again.
- **No reply after 5 days:** `mcp__tracker__followups_due`, then a follow-up via `write-dm`, kind `follow_up`. Max 2 follow-ups.

## 4. Tell her what matters
Lead with the hot ones: "2 brands replied. Fernway Coffee wants rates for a reel plus raw footage; a reply is in your queue."
