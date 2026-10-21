# Results — plain (A), controlled (B) and controlled with families v2 (C), 3 runs each

Model: claude-sonnet-5-5 for every run, 2026-10-21. Data: insurance_claims after the H-1.2 and £0-floor fixes (sha256 in data/MANIFEST.json). Scored by `scoring/score.py` against the dataset's answer key; detail per run in `scoring/detail/`.

| Measure | Plain (A) | Controlled (B) | Controlled, families v2 (C) |
|---|---|---|---|
| Genuine planted problems found | 6/6 in every run | 6/6 in every run | 6/6 in every run |
| Right rule cited | 6/6 in every run | 6/6 in every run | 6/6 in every run |
| Legitimate look-alikes wrongly flagged | 0 in every run | 0 in every run | 0 in every run |
| Unplanted: CLM-0034 excess not refunded after full recovery (R-03, M-1.2) | 2 of 3 runs | 3 of 3 runs | 3 of 3 runs |
| Unplanted: CLM-0001 complaint upheld for a courtesy car the policy doesn't include | 3 of 3 runs | 0 of 3 runs | 3 of 3 runs |
| Settlement figures matching the calculator (limit and excess findings) | 7 of 8 | 8 of 8 | 9 of 9 |
| Findings disputed by the checker sub-agent | n/a | 0 | 0 |
| Cost per run (USD) | 0.68–0.83, mean 0.74 | 0.88–1.03, mean 0.96 | 0.84–1.12, mean 0.99 |
| Model time per run (s) | 144–193, mean 163 | 210–267, mean 229 | 178–218, mean 196 |
| Tool calls per run | 18–27 | 41–51 | 29–35 |
| Answer-key access detected | 0 | 0 | 0 |

## Readings

0. C (families v2: F8 widened to whether a complaint outcome is supported) was the only design to get everything right in every run: all planted cases, no false flags, both unplanted issues, every settlement figure. Fixing the checklist removed the ceiling B showed.

1. On detection, the controls made no difference: an unaided Sonnet 5.5 found every planted problem with the right rule and flagged no legitimate claim.
2. The controls bought consistency, not detection: every B run flagged CLM-0034 and every B settlement figure matched the calculator; A missed CLM-0034 once and gave a gross figure where a net one was meant.
3. The checklist became a ceiling. F8 Complaints was defined as time limits only; every B run checked exactly that and none re-examined why CMP-005 was upheld. Every A run caught it.
4. The checker never disputed a finding in 3 runs. Either every finding was right (they were, on the planted cases) or the checker was too deferential; this test can't tell which.
5. Cost of the controls: about 30% more money, 40% more time, twice the tool calls.
6. Before any run, the controls (calculator, excess reconciliation) found an error in the answer key itself (CASE-06) and a negative recorded settlement (CLM-0017). Neither agent design would have.

## Scoring bugs found during the analysis

- Cases recorded only against invoice lines (CASE-07, CASE-08) couldn't be scored at first; fixed by tracing records to claims.
- Settlement accuracy first compared cover findings (correct answer £0) with the calculator (which assumes cover); fixed by limiting it to limit and excess findings.
