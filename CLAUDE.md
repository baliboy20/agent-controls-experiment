# Agent controls experiment: session briefing

Read this first. It brings a new Claude Code session in this folder up to date with what has been done, what was found, and what we intend to do next. Keep it current: when you finish a piece of work, update "Status" and "Next steps" below.

## What this project is

An experiment behind William Paulton's four-part Medium series *Recommendations When Building Agentic Apps for Enterprises*. The question: do eight enterprise "controls" still earn their place when the agent runs on a capable model? Three agent designs reviewed the same 99 synthetic insurance claims (Thameside Insurance, from the `claude-study-datasets` repo), three runs each, all on `claude-sonnet-5-5`, scored against the dataset's answer key.

- **A, plain:** one-paragraph brief and the database.
- **B, controlled:** the same plus all eight recommendations (source register, exception families with legitimate counterparts, tied-down brief, a settlement calculator built twice, data checks, an independent checker sub-agent, logging hooks).
- **C, corrected:** B with the complaints exception family widened after B's results.

The series is published on Medium. Parts 1–4 are drafted and maintained in a Claude Docs doc set (not in this repo). The public copy of this repo is `github.com/baliboy20/agent-controls-experiment`; the dataset is `github.com/baliboy20/claude-study-datasets`.

## Layout

| Path | Holds |
|---|---|
| `design/` | Experiment plan, the controlled agent's requirements, `findings.schema.json` |
| `data/` | Agent-safe copy of the claims database (answer-key tables and hints removed) and `MANIFEST.json` |
| `knowledge/` | Policy wording, procedures, staff authority, exception families (v2), glossary |
| `tools/calculator/` | Settlement calculator: spec, 16 hand-worked cases, Python and TypeScript builds, cross-check |
| `tools/controls/` | Data controls: checksum and row counts, control totals, excess reconciliation, invoice screen |
| `agents/run-a-plain/`, `agents/run-b-controlled/` | Prompts, `.claude/settings.json` (hooks and permissions), the `claims-checker` sub-agent brief |
| `hooks/log_event.py` | Logging hook: one JSON line per tool call, sub-agent stop and session stop |
| `runs/<id>/` | Each run's `workspace/`, `findings.json`, `log.jsonl`, `run.json`, `transcript.json` |
| `scoring/` | `score.py`, `results.csv`, `detail/` |
| `checker_test/` | Follow-up: plants mistakes in a real findings file and runs the checker on them |
| `article/results.md` | Results write-up used for Part 4 |
| `medium-tables/` | PNG renderings of the series' tables (Medium can't render tables) |

## How a run works

`python3 make_workspace.py <id>` builds `runs/<id>/workspace/` with only what that design may see, plus a `run.sh`. The id's first letter picks the design (`a-`, `b-`, `c-`). `MODEL=claude-sonnet-5-5 runs/<id>/workspace/run.sh` starts Claude Code headless (`claude -p`, project settings only, a fixed `--allowedTools` list) and writes the outputs to `runs/<id>/`. `python3 scoring/score.py` scores every run that has a `findings.json`; it needs `claude-study-datasets` cloned beside this folder for the answer key.

The nine original runs (a-1 to c-3) were made on 21 Oct 2026 with Claude Code 2.1.306. Do not rerun or overwrite them; `make_workspace.py` refuses an id that already has findings.

## Rules that keep the experiment honest

- **Never alter `data/claims.sqlite`** or anything in `knowledge/`. Every planted test lives in findings files, never in the data.
- **The answer key must never reach a workspace.** `make_workspace.py` checks for leaks; keep it that way. The key lives only in the dataset repo.
- **Keep model and tools fixed** across runs you intend to compare: `claude-sonnet-5-5`, the same `--allowedTools`.
- **Log everything.** The hooks in `.claude/settings.json` must stay; the logs are how we found the checker problem below.
- **Nothing here pays, declines or contacts anyone.** All findings are provisional assessments.
- Don't push to GitHub or edit the Medium articles without William; report and let him decide.

## What the study found (as published)

| Measure | A | B | C |
|---|---|---|---|
| Planted problems found, right rule cited | 6/6 every run | 6/6 every run | 6/6 every run |
| Legitimate counterparts wrongly flagged | 0 | 0 | 0 |
| Unplanted: excess not refunded | 2 of 3 runs | 3 of 3 | 3 of 3 |
| Unplanted: complaint upheld for cover the policy lacks | 3 of 3 | 0 of 3 | 3 of 3 |
| Settlement figures matching the calculator | 7/8 | 8/8 | 9/9 |
| Checker disputes | n/a | 0 | 0 |
| Average cost / model time per run | $0.74 / 163 s | $0.96 / 229 s | $0.99 / 196 s |

Conclusions: with a strong model the controls don't make the agent find more; they make it consistent, provable and auditable. Controls are only as good as the thinking behind them (B's deadlines-only complaints family made it miss what A found by reading). The tools also found two errors in the answer key before any agent ran. Building the calculator twice exposed two readings of the specification and a bug that 16 passing tests had not.

## The problem we are now fixing: the checker

Recommendation 5 (an independent checker) is the only one the study did not test:

1. The checker agreed with every finding in all six controlled runs, but it was never shown a mistake, so a careful checker and a rubber stamp would have scored the same.
2. The logs show the checker's **Bash calls were denied** in every run: sub-agents don't inherit `--allowedTools`, and `settings.json` had no `permissions.allow`. Its first attempt returned no verdicts; the main agent then extracted the records and sent them with the findings, and the checker agreed on that basis. So it never opened the database or reran the calculator itself, contrary to its brief.

Part 4 of the series now discloses both points ("Checker failure" in the conclusions) and promises a follow-up.

Fixes already made (commit `f4d8c8b`):

- `agents/run-b-controlled/.claude/settings.json` now has `permissions.allow` for Read, Glob, Grep, `Bash(python3:*)`, `Bash(sqlite3:*)`, which sub-agents do read.
- `checker_test/inject.py` plants 8 mistakes in a real design-C findings file (wrong clause, wrong rule, two wrong figures, wrong related claim, two legitimate counterparts flagged, one genuine finding removed) and leaves 3 genuine findings as controls; writes `draft.json` and `manifest.json`.
- `checker_test/run_checker.sh <id>` runs the checker alone on the planted draft in a fresh design-C workspace (`runs/c-<id>/`).
- `checker_test/score_checker.py` scores caught / missed / false disputes per run.

## Next steps (present intentions)

1. **Run the checker test**, three times:
   ```bash
   python3 checker_test/inject.py runs/c-1/findings.json checker_test/planted
   MODEL=claude-sonnet-5-5 checker_test/run_checker.sh chk-1   # then chk-2, chk-3
   python3 checker_test/score_checker.py checker_test/planted/manifest.json runs/c-chk-*/checker_verdicts.txt
   ```
   Before scoring, confirm in each `runs/c-chk-N/log.jsonl` that the checker's `sqlite3`/`python3` Bash calls succeeded (no denials) and that it reran the calculator for the figure findings. If Bash is still denied, stop and report; the test is meaningless without data access.
2. **Rerun the full controlled design** with the permissions fix (`c-4`, `c-5`, `c-6`) and check the logs show the checker querying the database itself. Score with `scoring/score.py` and compare with c-1 to c-3.
3. **Write up** the results as a short follow-up (`article/checker-followup.md`): dispute rate on planted mistakes, false disputes on genuine findings, whether the removed finding was noticed, and what changed when the checker had real access. Report to William; he decides what goes into Part 4 or a fifth piece.
4. Possible later work: a reasoning-type taxonomy across the six Thameside datasets (which tasks go to code, which to the model), as a fifth article.

## Status

- 2026-10-27: permissions fix and `checker_test/` added and pushed. No checker-test runs made yet. The nine original runs are untouched.
