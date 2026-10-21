# Scoring

`score.py` (to do) reads a run's `findings.json` and the answer key in the dataset folder:

- `046-study-data-sets/datasets/insurance_claims/docs/planted-cases.md`
- `046-study-data-sets/datasets/insurance_claims/packs/ai-eval/expected-answers.json`

It writes one row per run to `results.csv`, with the measures in `design/experiment-plan.md`. This folder is never copied into a run workspace.
