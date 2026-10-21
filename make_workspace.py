#!/usr/bin/env python3
"""Build an isolated workspace for one run.

Usage (from the project root):  python3 make_workspace.py a-1 | b-2 ...

Creates runs/<id>/workspace/ with only what that design gets (see design/experiment-plan.md), plus run.sh.
Never copies scoring/, design/ (except the schema), or anything that points at the answer key.
"""
import json, os, shutil, sys
ROOT = os.path.dirname(os.path.abspath(__file__))

def cp(src, dst):
    s, d = os.path.join(ROOT, src), dst
    os.makedirs(os.path.dirname(d), exist_ok=True)
    if os.path.isdir(s): shutil.copytree(s, d, dirs_exist_ok=True, ignore=shutil.ignore_patterns("__pycache__", ".gitkeep", "*.sqlite-journal"))
    else: shutil.copyfile(s, d)

def build(run_id):
    design = run_id.split("-")[0]
    if design not in ("a", "b", "c"): sys.exit("run id must start a-, b- or c-")
    # c = controlled design with exception families v2 (F8 widened); same agent files as b
    agent = "run-a-plain" if design == "a" else "run-b-controlled"
    rd = os.path.join(ROOT, "runs", run_id); ws = os.path.join(rd, "workspace")
    if os.path.exists(os.path.join(rd, "findings.json")): sys.exit(f"{run_id} already has findings.json; refusing to overwrite")
    if os.path.exists(ws): shutil.rmtree(ws, ignore_errors=True)
    os.makedirs(ws, exist_ok=True)
    W = lambda *p: os.path.join(ws, *p)
    cp("data/claims.sqlite", W("claims.sqlite"))
    m = json.load(open(os.path.join(ROOT, "data", "MANIFEST.json")))
    json.dump({"file": m["file"], "sha256": m["sha256"], "row_counts": m["row_counts"]}, open(W("MANIFEST.json"), "w"), indent=2)  # no source path
    cp("design/findings.schema.json", W("findings.schema.json"))
    cp(f"agents/{agent}/prompt.md", W("prompt.md"))
    cp(f"agents/{agent}/.claude/settings.json", W(".claude", "settings.json"))
    cp("hooks/log_event.py", W(".hooks", "log_event.py"))
    os.makedirs(W("output"), exist_ok=True)
    if design in ("b", "c"):
        cp("knowledge", W("knowledge"))
        cp("tools/controls/controls.py", W("tools", "controls", "controls.py"))
        cp("tools/calculator/SPEC.md", W("tools", "calculator", "SPEC.md"))
        cp("tools/calculator/settle.py", W("tools", "calculator", "settle.py"))
        cp("tools/calculator/python/calc.py", W("tools", "calculator", "python", "calc.py"))
        cp(f"agents/{agent}/claims-checker.md", W(".claude", "agents", "claims-checker.md"))
    run_sh = f"""#!/usr/bin/env bash
# Run {run_id}. Usage: MODEL=<model id> ./run.sh   (check flags with `claude --help` before the first run)
set -euo pipefail
cd "$(dirname "$0")"
: "${{MODEL:?set MODEL to the model id, the same for every run}}"
export RUN_LOG="$(cd .. && pwd)/log.jsonl"
python3 - <<PY
import json, hashlib, datetime, subprocess
v = subprocess.run(["claude", "--version"], capture_output=True, text=True).stdout.strip()
json.dump({{"run_id": "{run_id}", "design": "{design.upper()}", "model": "$MODEL", "claude_version": v,
           "started": datetime.datetime.now(datetime.timezone.utc).isoformat(),
           "data_sha256": hashlib.sha256(open("claims.sqlite","rb").read()).hexdigest()}},
          open("../run.json", "w"), indent=2)
PY
# Project settings only (hooks, deny rules); no user plugins, MCP servers, skills or saved sessions.
env -u CLAUDE_CODE_ADDITIONAL_DIRECTORIES_CLAUDE_MD -u CLAUDE_CODE_SESSION_ID \\
claude -p "$(cat prompt.md)" --model "$MODEL" --output-format json \\
  --setting-sources project --strict-mcp-config --disable-slash-commands --no-session-persistence \\
  --allowedTools "Read" "Glob" "Grep" "Bash(python3:*)" "Bash(sqlite3:*)" "Write(output/**)" "Edit(output/**)" "Agent" \\
  > ../transcript.json
cp output/findings.json ../findings.json
python3 - <<PY
import json, datetime
m = json.load(open("../run.json")); m["finished"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
json.dump(m, open("../run.json", "w"), indent=2)
PY
echo "{run_id} done: runs/{run_id}/findings.json"
"""
    open(W("run.sh"), "w").write(run_sh); os.chmod(W("run.sh"), 0o755)
    files = sorted(os.path.relpath(os.path.join(d, f), ws) for d, _, fs in os.walk(ws) for f in fs)
    leak = [f for f in files if "truth" in f or "planted" in f or "expected" in f or "scoring" in f]
    for f in files:
        if f.endswith((".py", ".md", ".json", ".sh")) and "046-study" in open(W(f), errors="ignore").read(): leak.append(f)
    if leak: sys.exit(f"answer-key material in workspace: {leak}")
    print(json.dumps({"run": run_id, "workspace": os.path.relpath(ws, ROOT), "files": files}, indent=2))

if __name__ == "__main__":
    if len(sys.argv) != 2: print(__doc__); sys.exit(2)
    build(sys.argv[1])
