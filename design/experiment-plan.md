# Experiment plan

## Question

On the same claims review, does a controlled agent (run B) find more genuine problems, wrongly flag fewer legitimate claims, and calculate settlements more accurately than a plain agent (run A)?

## Task given to both runs

Review the 99 claims notified in September 2026 and list every claim that needs a claims handler's attention, with the rule and clause behind each finding and, where a settlement is wrong, the correct amount. Output must follow `design/findings.schema.json`.

## Fixed across runs

- Same model and version, recorded in each `run.json`.
- Same data file, checked against `data/MANIFEST.json` before each run.
- Same output schema and the same logging hooks.
- Read-only access to data. No network.

## Isolation

Each run executes in `runs/<id>/workspace/`, built fresh by a workspace builder (to do):

| Run | Workspace contains |
|---|---|
| A | `claims.sqlite`, `prompt.md`, `findings.schema.json`, hooks settings |
| B | The above, plus `knowledge/`, `tools/` (calculator and controls), the checker sub-agent and run-B prompt |

Neither workspace contains `scoring/`, this plan, or any path to `046-study-data-sets`. The workspace is deleted after the run; only `findings.json`, `log.jsonl` and `run.json` are kept.

## Scoring

Scored against the dataset's answer key (`docs/planted-cases.md`, `packs/ai-eval/expected-answers.json`) by `scoring/`.

| Measure | Definition |
|---|---|
| Genuine problems found | Planted genuine cases flagged, with the right claim ID |
| Right reason | Of those, cited the correct rule or clause |
| Legitimate claims wrongly flagged | Planted look-alike cases flagged as problems |
| Other flags | Claims flagged that are not planted cases; reviewed by hand |
| Settlement accuracy | Corrected settlements within £0.01 of the expected figure |
| Cost and time | Tokens, tool calls and wall-clock time, from the log |

Each measure is reported per run and as the mean and range over the 3 runs per design.

## Run order

1. Build and test the calculator against `tools/calculator/golden/cases.json` in both languages.
2. Build controls and the workspace builder; dry-run both designs on 5 claims.
3. Run A1–A3, then B1–B3, on the full extract.
4. Score, then review the "other flags" by hand.

## Follow-up runs C1–C3

Same as B, with `knowledge/exception-families.md` v2: F8 Complaints widened to cover whether a complaint's outcome is supported by the wording and evidence. Tests whether fixing the checklist removes the gap B1–B3 showed on complaint substance.
