"""PostToolUse hook: append every tracker call to data/audit.log.

One line per call: when, which tool, what went in, and a short version of what came back.
Useful when you want to know exactly what the agent did while you were asleep.
"""
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

call = json.load(sys.stdin)
line = {
    "at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    "tool": call.get("tool_name"),
    "input": call.get("tool_input"),
    "output": str(call.get("tool_response"))[:300],
}
log = Path(__file__).resolve().parents[2] / "data" / "audit.log"
log.parent.mkdir(exist_ok=True)
with log.open("a", encoding="utf-8") as f:
    f.write(json.dumps(line) + "\n")
