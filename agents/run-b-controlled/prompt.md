# Claims review — September 2026

## Objective

Review the 99 claims in `claims.sqlite` (home and motor claims notified to Thameside Insurance from 1 to 30 September 2026) and find every claim that needs a claims handler's attention. A handler will act on your findings, so a missed problem and a wrongly flagged good claim both cost money: one in overpayment, the other in an unfair delay to a customer under the FCA's Consumer Duty.

## What you have

| Resource | Use it for |
|---|---|
| `knowledge/policy-clauses.md` | The policy wording. Authoritative for cover, limits, excesses, exclusions, conditions |
| `knowledge/procedures.md` | Rules R-01 to R-08 the claims team must follow |
| `knowledge/exception-families.md` | The eight families of problem to check, each with its legitimate counterpart |
| `knowledge/staff-authority.md`, `knowledge/glossary.md` | Settlement authority; terms |
| `tools/calculator` | Correct settlement for an accepted claim. Use it for every settlement figure |
| `tools/controls/controls.py` | Data checks. Run `verify` before you start |
| `claims-checker` sub-agent | Independent review of your findings before you write them |

## Requirements

1. Run `python3 tools/controls/controls.py verify` first. If it fails, stop and report the failure.
2. Check every exception family against all 99 claims. Record each family's check, including when it finds nothing.
3. Before recording a finding, check the family's legitimate counterpart and say why it does not apply.
4. Take every settlement figure from the calculator. Do not calculate settlements yourself.
5. Cite at least one rule ID, and the clause ID where one applies, in every finding.
6. Send all findings to the `claims-checker` sub-agent. Drop a finding it disputes, or keep it with `checker_status: "Disputed"` and your reason.
7. Your findings are provisional assessments. Never state that a claim is approved, declined or paid.

## Never

- Write to `claims.sqlite` or to any file outside `output/`.
- Read files outside this workspace, or use the network.

## Done when

`output/findings.json` validates against `findings.schema.json`, every family has a recorded check, and the checker has reviewed every finding.
