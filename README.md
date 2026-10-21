# Agent controls experiment

Does an AI agent built with enterprise controls do better than a plain one? This repository holds the experiment behind the Medium series *Recommendations When Building Agentic Apps for Enterprises*: the agent briefs, knowledge base, tools, logging, scoring, and every run's output.

Three agent designs reviewed the same 99 insurance claims from the [Thameside insurance claims dataset](https://github.com/baliboy20/claude-study-datasets/tree/main/datasets/insurance_claims), three runs each, all on `claude-sonnet-5-5`, and were scored against the dataset's answer key.

| Design | Given |
|---|---|
| A, plain | A one-paragraph brief and the claims database |
| B, controlled | The same, plus a knowledge base, exception families, a tied-down brief, a settlement calculator, data controls, an independent checker sub-agent and logging hooks |
| C, controlled and corrected | B with the complaints exception family widened after B's results |

## Results

| Measure | Plain (A) | Controlled (B) | Controlled, corrected (C) |
|---|---|---|---|
| Planted problems found, right rule cited | 6/6 every run | 6/6 every run | 6/6 every run |
| Legitimate counterparts wrongly flagged | 0 | 0 | 0 |
| Unplanted: excess not refunded after the other insurer paid in full | 2 of 3 runs | 3 of 3 runs | 3 of 3 runs |
| Unplanted: complaint upheld for a courtesy car the policy doesn't include | 3 of 3 runs | 0 of 3 runs | 3 of 3 runs |
| Settlement figures matching the calculator | 7 of 8 | 8 of 8 | 9 of 9 |
| Average cost and model time per run | $0.74, 163 s | $0.96, 229 s | $0.99, 196 s |

Full results and readings: [`article/results.md`](article/results.md). Per-run scoring: [`scoring/results.csv`](scoring/results.csv) and [`scoring/detail/`](scoring/detail/).

Nine runs on one synthetic dataset with one model show where controls change behaviour; they are not a benchmark.

## Layout

| Path | Holds |
|---|---|
| `design/` | Experiment plan, the controlled agent's requirements, findings schema |
| `data/` | Agent-safe copy of the claims database (answer-key tables and hints removed) and its manifest |
| `knowledge/` | Policy wording, procedures, staff authority, exception families (v2), glossary |
| `tools/calculator/` | Settlement calculator: spec, 16 hand-checked cases, Python and TypeScript implementations built independently, cross-check |
| `tools/controls/` | Data controls: checksum and row counts, control totals, excess reconciliation, invoice screen |
| `agents/` | Prompts, Claude Code settings and the checker sub-agent |
| `hooks/` | Logging hook: one JSON line per tool call, sub-agent stop and session stop |
| `runs/` | Each run's `findings.json`, `log.jsonl`, `run.json` and `transcript.json` |
| `scoring/` | Scoring script and results |
| `make_workspace.py` | Builds an isolated workspace and `run.sh` for one run |

Paths in the logs and transcripts are shortened to `<workspace>`, `<agent-scratch>` and `<agent-session>`, and session IDs to `<session-id>`.

## Reproducing

You need Python 3.10+, Node.js 22.18+ (for the TypeScript calculator) and Claude Code.

```bash
# Tests and cross-check
(cd tools/calculator/python && python3 test_calc.py)
(cd tools/calculator/typescript && node --test test_calc.ts)
python3 tools/calculator/crosscheck/crosscheck.py
python3 tools/controls/controls.py verify

# A run (use a new id, e.g. a-4)
python3 make_workspace.py a-4
MODEL=claude-sonnet-5-5 runs/a-4/workspace/run.sh

# Scoring: clone claude-study-datasets beside this repository first
python3 scoring/score.py
```

Run agents on a machine that does not hold the answer key. Scoring reads it from the dataset repository after the run.

## Dataset version

The runs used the insurance claims dataset after two fixes to its generator: a claim under both Buildings and Contents carries an excess for each section (clause H-1.2), and a proposed settlement is never negative. `data/MANIFEST.json` records the source file's checksum.

## Licence

Code is MIT ([`LICENSE`](LICENSE)). Data, documents and run outputs are CC BY 4.0 ([`LICENSE-DATA.md`](LICENSE-DATA.md)), derived from the [Synthetic UK financial-services study datasets](https://github.com/baliboy20/claude-study-datasets), © 2026 William Paulton.
