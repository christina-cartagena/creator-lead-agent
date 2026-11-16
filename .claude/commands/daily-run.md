---
description: Run the whole lead pipeline once - find, screen, match, draft, critique, queue, and check replies.
---

Run today's outreach pipeline. Follow the graph in `agent/graph.py` in order:

1. `mcp__tracker__pipeline_status` and note the starting funnel.
2. **check-replies** skill first, so hot leads are handled before anything new.
3. **find-prospects** skill, up to the daily limit.
4. **pick-portfolio-piece** skill.
5. **write-dm** skill for every `matched` prospect, up to `daily_limits.drafts`. Each draft goes through the **dm-critic** subagent; only 7+ are saved. Run critic calls for different brands in parallel.
6. `mcp__tracker__followups_due`, and draft follow-ups the same way.
7. `mcp__tracker__pipeline_status` again.

Finish with a short briefing for the creator, hot replies first:
- Replies and what each brand wants
- New drafts waiting in the queue (count, and the top 3 by score)
- Brands skipped and why (past clients, duplicates)
- "Open your queue: python -m agent queue"

Do not send anything. $ARGUMENTS
