---
name: find-prospects
description: Find brands worth pitching for UGC work. Use when asked to find leads, prospects, brands to contact, or at the start of the daily run. Searches the web for brands in the creator's niches that show a buying signal, checks each against past clients and earlier outreach, and adds the good ones to the tracker.
---

# Find prospects

Goal: a short list of brands that are likely to pay for UGC **this month**, each with a specific, verifiable reason.

## 1. Read the brief

Read `config/creator.json` (or `creator.example.json`): niches, `ideal_brand.signals`, `ideal_brand.avoid`, follower range and `daily_limits.new_prospects`.

## 2. Search for buying signals

For each niche, run a few searches. Good patterns:

- `"<niche>" brand "UGC creators" OR "creator callout"` limited to the last 30 days
- `"<niche>" new product launch` + `DTC` or `small brand`, last 30 days
- Brand posts using `#ugccreatorwanted` or `#ugcopportunity`
- Product Hunt, Shopify blog features, and trade press for new DTC launches in the niche

Open the brand's site and public Instagram page to confirm. A signal counts only if you can point to it:

| Strong signal | Why it matters |
|---|---|
| Posted a creator or UGC callout | They are actively buying |
| Launched a product in the last 30 days | They need content for it now |
| Reposts customer videos | They want UGC and are getting it free |
| Feed is all product shots, no people | Obvious gap a creator fills |

Skip anything in `ideal_brand.avoid`, outside the follower range, or without a working website.

## 3. Check before you add

For every candidate, call `mcp__tracker__check_brand` with brand, handle and email.
- `known: true` as past_client: do **not** add. Note it in your summary ("Haven Candle is a past client, last project March").
- `known: true` as prospect: do not add again.

## 4. Add the keepers

`mcp__tracker__add_prospect` with:
- `why`: one sentence, specific and dated. Good: "Launched a vitamin C serum on Nov 3 and is reposting customer videos." Bad: "Great skincare brand."
- `source`: where you found it (search query or URL)
- `niche`: one of the creator's niches, spelled the same way

Stop at `daily_limits.new_prospects`.

## 5. Optional: Instagram Business Discovery

If `IG_ACCESS_TOKEN` and `IG_USER_ID` are set, the official Graph API can return another business account's follower count and recent posts:
`GET /{ig-user-id}?fields=business_discovery.username(<handle>){followers_count,media_count,media.limit(6){caption,timestamp,media_type}}`
Use it to confirm follower counts and recent launches. Never scrape Instagram.

## Output

End with a table: brand, handle, niche, signal, and whether it was added or skipped (and why).
