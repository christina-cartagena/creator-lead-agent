---
name: pick-portfolio-piece
description: Choose which single portfolio piece to send a brand. Use after prospects are screened, or when asked which example to show a brand. Runs the deterministic matcher, then sanity-checks its pick against what the brand actually sells and posts.
---

# Pick the portfolio piece

One brand, one piece. A single great example beats a link to everything.

1. Call `mcp__tracker__screen_and_match`. It skips past clients and duplicates, then scores every portfolio item against each prospect (same niche, tag overlap, proven result) and stores the top pick with its reason.
2. For each matched prospect, read the pick (`mcp__tracker__get_portfolio_item`) and the prospect's `why`. Ask: would this brand's marketing lead watch this and picture *their* product in it?
   - Same product category beats same niche label.
   - A piece with a real result ("brand reused it as a paid ad") beats one without, when fit is close.
   - If the brand's gap is "no people on the feed", favour a piece with a face on camera.
3. If the matcher's pick is wrong, say which piece you would use instead and why, and use that one when drafting. Do not invent pieces.

Report: brand, chosen piece, one-line reason.
