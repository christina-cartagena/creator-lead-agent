---
name: write-dm
description: Write a first-touch Instagram DM or email to a brand, a follow-up, or a reply, in the creator's voice. Use whenever outreach copy is needed. Every draft goes to the dm-critic subagent and is saved only if it scores 7 or more.
---

# Write the message

## Inputs
- The prospect (`mcp__tracker__list_prospects` status `matched`, or `conversation` for follow-ups and replies)
- The chosen portfolio piece (`mcp__tracker__get_portfolio_item`)
- Voice rules in `config/creator.json`

## Channel
Instagram DM if there is a handle and no email, or the signal came from Instagram. Email if there is a partnerships or collabs address. One channel per brand per touch.

## Shape of a first-touch DM (under 90 words)
1. **Them first.** One line on the specific thing from `why`. Proves this is not a blast.
2. **The gap.** What content would help, in their terms.
3. **The proof.** The one portfolio piece, with its link and its result if it has one.
4. **Soft ask.** A low-effort next step: "Want me to send a quick idea for the serum launch?"
5. Sign off with `voice.sign_off` and her first name.

Email: same bones, under 160 words, plus a short subject line on the first line as `Subject: ...`.

## Follow-up (after 5 quiet days, max 2)
Two or three lines. Add something new (an idea, a hook, a relevant result). Never "just following up."

## Reply to an interested brand
Answer exactly what they asked. If they want rates, say she will send her rate card and ask one scoping question (number of videos, usage rights, timeline). Do not quote prices yourself.

## Before saving
1. Hand the draft, the prospect row and the portfolio piece to the **dm-critic** subagent.
2. Under 7: apply its notes and re-score. Max 3 rounds, then skip the brand and say why.
3. 7 or more: `mcp__tracker__save_draft` with the score and the critic's one-line note.
   `save_draft` also lints in code (length, one link, banned phrases, no placeholders). If it refuses, fix and retry.

Never send. Saved drafts wait in the approval queue for her.
