#!/usr/bin/env bash
# Run the claims-checker, on its own, over a planted draft. Usage (from the project root):
#   MODEL=claude-sonnet-5-5 checker_test/run_checker.sh chk-1 [checker_test/planted/draft.json]
# Builds a design-C workspace for the run, drops the draft in, and starts the checker with the same brief
# and permissions a sub-agent gets (Read + Bash; no Agent). Output: runs/<id>/checker_verdicts.txt and log.jsonl.
set -euo pipefail
cd "$(dirname "$0")/.."
: "${MODEL:?set MODEL to the model id}"
ID="${1:?run id, e.g. chk-1}"; DRAFT="${2:-checker_test/planted/draft.json}"
python3 make_workspace.py "c-${ID}" > /dev/null          # c-chk-1: design C files, no answer key
WS="runs/c-${ID}/workspace"
mkdir -p "$WS/scratchpad"; cp "$DRAFT" "$WS/scratchpad/draft.json"
export RUN_LOG="$(cd "runs/c-${ID}" && pwd)/log.jsonl"
BRIEF="$(awk 'f>=2{print} /^---$/{f++}' "$WS/.claude/agents/claims-checker.md")"   # body after the front matter
PROMPT="$BRIEF

Independently review the draft findings in scratchpad/draft.json against this workspace (claims.sqlite read-only, knowledge/*.md, tools/). Return one line per finding: claim ID, family, Agreed or Disputed, and a reason of at most 40 words. Read-only; write nothing."
( cd "$WS" && env -u CLAUDE_CODE_ADDITIONAL_DIRECTORIES_CLAUDE_MD -u CLAUDE_CODE_SESSION_ID \
  claude -p "$PROMPT" --model "$MODEL" --output-format json \
    --setting-sources project --strict-mcp-config --disable-slash-commands --no-session-persistence \
    --allowedTools "Read" "Glob" "Grep" "Bash(python3:*)" "Bash(sqlite3:*)" \
  > ../transcript.json )
python3 - "runs/c-${ID}" <<'PY'
import json, sys
d = json.load(open(f"{sys.argv[1]}/transcript.json"))
txt = d.get("result") if isinstance(d, dict) else "\n".join(m.get("result", "") for m in d if isinstance(m, dict))
open(f"{sys.argv[1]}/checker_verdicts.txt", "w").write(txt or "")
print(txt)
PY
echo "verdicts: runs/c-${ID}/checker_verdicts.txt   log: runs/c-${ID}/log.jsonl"
