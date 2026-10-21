# Settlement calculator — specification v0.3

Computes the correct settlement for a claim that has been accepted. It does not decide cover, exclusions, evidence or declines; those are rule checks (R-01, R-04, R-06). Two independent implementations (Python, TypeScript) must both pass every case in `golden/cases.json`, and must agree on every claim in the dataset.

## Input

```json
{
  "case_id": "G01",
  "product": "Home | Motor (or a full product name such as \"Motor - Comprehensive\"; see D-5)",
  "claim_type": "value of claims.claim_type",
  "policy": {
    "buildings_sum_insured_gbp": 0, "contents_sum_insured_gbp": 0,
    "single_article_limit_gbp": 0, "specified_items": [{"description": "", "value_gbp": 0}],
    "excess_standard_gbp": 0, "excess_escape_of_water_gbp": 0,
    "excess_compulsory_gbp": 0, "excess_voluntary_gbp": 0, "excess_windscreen_gbp": 0,
    "vehicle_value_gbp": 0
  },
  "items": [{"item_id": "", "section": "Buildings | Contents | Motor", "category": "value of claim_items.category",
             "agreed_amount_gbp": 0, "specified_item": "description, or null"}]
}
```

Missing or null policy amounts are treated as not applicable, never as zero cover.

## Output

```json
{
  "case_id": "G01",
  "sections": {"Buildings": {"items_allowed_gbp": 0, "cap_gbp": 0, "capped_total_gbp": 0, "excess_gbp": 0, "settlement_gbp": 0}},
  "excess_total_gbp": 0,
  "settlement_total_gbp": 0,
  "clauses_applied": ["H-4.1"],
  "warnings": []
}
```

## Rules, applied in this order per section

| Step | Rule | Clause |
|---|---|---|
| 0 | **Product.** Use the text before the first " - " of `product`: `Home` or `Motor`. Anything else is an error. | D-5 |
| 1 | **Valuables, per item.** For an item with category `Valuables`: if `specified_item` matches an entry in `policy.specified_items` (ignoring case, leading and trailing spaces, and repeated spaces; see D-4), allow up to that entry's `value_gbp`; otherwise allow up to `single_article_limit_gbp`. | H-3.2 |
| 2 | **Valuables, in total.** Allowed valuables in the claim are limited in total to one third of `contents_sum_insured_gbp` (see D-1). | H-3.2 |
| 3 | **Trace and access.** For claim type `Escape of water`, items with category `Trace and access` are limited in total to £5,000. | H-2.2 |
| 4 | **Section total.** Sum the allowed items per section, then cap at the section's limit: Buildings → buildings sum insured; Contents → contents sum insured; Motor → `vehicle_value_gbp`. | H-4.1, M-3.1 |
| 5 | **Excess per section.** Home: `Escape of water` → escape of water excess; `Subsidence` → £1,000; otherwise standard excess. Every Home section claimed carries its own excess. Motor: `Windscreen - repair` → £0; `Windscreen - replacement` → windscreen excess; otherwise compulsory + voluntary excess. | H-1.2, M-1.2 |
| 6 | **Settlement per section** = max(0, capped total − excess). | H-4.1, M-3.1 |
| 7 | **Rounding.** All money to 2 decimal places, half up, at each step. | Conventions |

Steps 2 and 3 apply to the whole claim, across sections (D-3). Where one reduces a total, the reduction is shared between sections in proportion to each section's amount subject to that cap, each share rounded half up, with the last section in the order Buildings, Contents, Motor taking the rounding remainder. A warning names the cap.

## Out of scope

- Excess refunds on non-fault motor claims (M-1.2). This is a payment event, checked by controls under R-03.
- Interim payments, recoveries and salvage. The calculator returns what should be paid in total; controls compare it with payments.

## Decisions

Confirmed by William, 2026-10-21. D-3 to D-5 were found when the two implementations read v0.2 differently.

| ID | Question | Decision | Why it matters |
|---|---|---|---|
| D-1 | Does the one-third valuables limit include specified items? | Yes, specified items count towards the limit: H-3.2 says "valuables in total" without an exception | Changes the settlement for any claim with a large specified item and a small contents sum insured |
| D-2 | Does a claim with no Valuables items but a section total above the sum insured get capped before or after excess? | Cap first, then subtract excess (H-4.1 "the sum insured ... less the excess") | Changes settlements at the cap by the amount of the excess |
| D-3 | Are the trace-and-access and valuables caps per claim or per section? | Per claim, shared between sections pro rata | Changes an escape-of-water claim with trace and access under both Buildings and Contents |
| D-4 | How is a specified item matched to the schedule? | Ignoring case, leading and trailing spaces, and repeated spaces | Exact matching silently drops a specified value over a capital letter |
| D-5 | The database's product names are longer than Home or Motor | Text before the first " - " | Without it, a motor claim can be priced with home excess rules |
