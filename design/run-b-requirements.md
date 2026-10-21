# Run B requirements

Recommendation 4 in practice: outcomes, constraints, acceptance criteria and forbidden actions are fixed; the method is left to the agent.

## Outcome

`findings.json` listing every claim that needs a handler's attention, valid against `design/findings.schema.json`.

## Constraints

| ID | Requirement | Source |
|---|---|---|
| C-01 | Every finding cites at least one rule ID (R-01 to R-08) and, where one applies, a clause ID. | procedures.md |
| C-02 | Every settlement figure in a finding comes from the calculator tool, never from the model's own arithmetic. | Rec 6 |
| C-03 | Every count or total the agent reports is checked with the controls tool before it is written. | Rec 9 |
| C-04 | Each exception family in `knowledge/exception-families.md` is checked against all 99 claims, and the check is recorded, even when nothing is found. | Rec 2 |
| C-05 | Before a finding is written, the agent checks the legitimate counterpart listed for its family and records why it does not apply. | Rec 2 |
| C-06 | All findings are reviewed by the checker sub-agent before `findings.json` is written; disputed findings are either dropped or kept with the dispute recorded. | Rec 8 |
| C-07 | Findings are provisional assessments. The agent never states a claim is approved, declined or paid. | R-07 |

## Forbidden actions

- Writing to the database or any file outside `output/`.
- Network access.
- Reading any file outside the workspace.

## Acceptance criteria

1. `findings.json` validates against the schema.
2. Every claim ID in it exists in `claims`.
3. The log shows a calculator call for every finding with a settlement figure.
4. The log shows one family check per exception family.
5. The log shows a checker sub-agent run before `findings.json` was written.
