"""PreToolUse hook: the agent drafts, a human sends.

Claude Code runs this before EVERY tool call and passes the call as JSON on stdin.
If the call would send, post, follow or DM anything, we deny it and tell Claude why.
A rule in a prompt can be forgotten; a hook cannot.
"""
import json
import re
import sys

call = json.load(sys.stdin)
tool = call.get("tool_name", "")
args = json.dumps(call.get("tool_input", {})).lower()

# Tools that would put words in front of another person.
SEND_TOOL = re.compile(r"(send|reply|post|publish|forward|follow|comment|dm)(_|$)", re.I)
# Drafting tools are fine: they wait for a human.
DRAFT_TOOL = re.compile(r"(draft|save_draft|create_draft)", re.I)

reasons = []
if SEND_TOOL.search(tool.split("__")[-1]) and not DRAFT_TOOL.search(tool):
    reasons.append(f"{tool} would send something")
if tool == "Bash" and re.search(r"graph\.facebook\.com.*/messages|instagram\.com/api|smtp|sendmail", args):
    reasons.append("shell command looks like it sends a message")
if tool.startswith("mcp__claude-in-chrome__") and "instagram.com/direct" in args:
    reasons.append("browser automation inside Instagram DMs")

if reasons:
    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": (
                "Blocked by guard_send: " + "; ".join(reasons) +
                ". This agent only drafts. Save it with mcp__tracker__save_draft and the creator will send it."
            ),
        }
    }))
sys.exit(0)
