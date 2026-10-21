#!/usr/bin/env python3
"""Claude Code hook: append one JSON line per event to the run log.

Reads the hook payload from stdin. Writes to $RUN_LOG, or log.jsonl in the project dir.
Never blocks the agent: always exits 0.
"""
import json, os, sys, datetime

def clip(v, n=2000):
    s = v if isinstance(v, str) else json.dumps(v, default=str)
    return s if len(s) <= n else s[:n] + f"...[{len(s)} chars]"

try:
    p = json.load(sys.stdin)
    rec = {
        "ts": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "event": p.get("hook_event_name"),
        "session_id": p.get("session_id"),
        "tool": p.get("tool_name"),
        "input": clip(p.get("tool_input")) if "tool_input" in p else None,
        "response": clip(p.get("tool_response")) if "tool_response" in p else None,
    }
    path = os.environ.get("RUN_LOG") or os.path.join(os.environ.get("CLAUDE_PROJECT_DIR", "."), "log.jsonl")
    with open(path, "a") as f:
        f.write(json.dumps(rec) + "\n")
except Exception as e:
    sys.stderr.write(f"log_event: {e}\n")
sys.exit(0)
