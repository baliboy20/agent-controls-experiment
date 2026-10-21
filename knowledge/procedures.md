# Claims procedures
Source: `_meta_rules` table in `data/claims.sqlite`. Every finding must cite at least one rule ID from this file.

## R-01 — Period of cover

*Area:* Cover · *Tables:* claims, policies

Before accepting a claim, the handler checks that the incident date falls within the period of insurance, using first_incepted and cover_start in policies. An incident in an earlier period of a renewed policy is covered under that period. An incident before the policy was first taken out is not covered (H-1.1, M-1.1); the claim is referred to Claims Validation. The policy status recorded on the claim does not show this.

## R-02 — Limits

*Area:* Settlement · *Tables:* claims, claim_items, policies, policy_clauses

A proposed settlement may not exceed the sum insured for the section claimed under, or the car's market value, less the excess (H-4.1, M-3.1). Any one valuable is limited to the single article limit unless it is specified on the schedule, when its specified value applies (H-3.2).

## R-03 — Excess

*Area:* Settlement · *Tables:* claims, claim_payments, policy_clauses

The excess recorded on the claim is taken once, from the first payments made on the claim, whether to the policyholder or to a supplier. A claim under both Buildings and Contents carries the excess for each section (H-1.2). The excess deducted across all payments on a claim must never exceed the excess recorded on it. On a non-fault motor claim the excess is refunded once the other insurer has paid in full (M-1.2).

## R-04 — Evidence before settlement

*Area:* Evidence · *Tables:* claims, claim_items, policy_clauses

A settlement may be proposed only when evidence_status is Complete: proof of ownership and value for any item over £500 (H-6.2), a police crime reference for theft and malicious damage (H-6.1, M-5.1), and a supplier invoice or agreed estimate for repairs. A reserve may be set while evidence is awaited.

## R-05 — Invoice checks

*Area:* Suppliers · *Tables:* claim_items, claim_payments, suppliers

Before paying a supplier invoice, the handler checks that the same work, equipment or invoice has not been charged to another claim. Invoices from the same supplier with matching amounts or overlapping hire dates are referred to Claims Validation before payment.

## R-06 — Declining a claim

*Area:* Decisions · *Tables:* claims, claim_items, policy_clauses, staff

A claim may be declined only under a clause in the policy wording that applies to the facts, recorded in decline_clause_id, and supported by the evidence on the claim, such as a supplier's report. Declines are approved by a Claims Team Leader or above. If the evidence contradicts the clause, the claim is accepted.

## R-07 — Settlement authority

*Area:* Decisions · *Tables:* claims, staff

A proposed settlement becomes final only when approved by someone whose settlement authority covers it: Claims Handler £5,000; Claims Team Leader £25,000; Claims Manager £100,000; Head of Claims £250,000. Until then it is a provisional assessment.

## R-08 — Complaint handling

*Area:* Complaints · *Tables:* complaints, claim_payments

Complaints follow the FCA's complaint-handling rules (DISP). A complaint resolved by the close of the third business day after receipt may be closed with a summary resolution. Otherwise a final response is sent within eight weeks, with the policyholder's right to refer to the Financial Ombudsman Service. A complaint about a decline is reviewed against the wording and the evidence, not the original decision alone. Redress is paid within 10 working days of the outcome.
