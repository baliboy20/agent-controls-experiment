# Notes: spec ambiguities and how calc.ts reads them (SPEC v0.3)

## Settled by v0.3 (previously my own reading)
- **Specified item matching (D-4):** this replaces my v0.2 exact match.
- **Steps 2 and 3 per claim, pro rata (D-3):** the remainder now goes to the last section in the order Buildings, Contents, Motor. Before, it went to whichever section came last in the input.
- **Product (D-5):** step 0 now applies.

## Still my reading
- **Step 0 is strict.** The prefix must be exactly `Home` or `Motor`: case-sensitive, nothing trimmed, and the separator must be exactly `" - "`. So `home`, `" Home"` and `Motor-Comprehensive` are errors.
- **Errors are thrown.** `calculate()` throws an Error. The CLI prints `{case_id, error}` for that case, carries on with the rest of a list, and exits 1.
- **What D-4 normalisation covers.** "Spaces" means the space character only. Tabs and other whitespace are neither trimmed nor collapsed. Case folding uses JS `toLowerCase()`, which differs from Python `casefold()` for a few characters such as ß. This could diverge from the Python implementation on unusual data.
- **Duplicate schedule entries.** If several entries match after normalisation, the first one wins.
- **Pro-rata shares.** Each share is reduction × section amount ÷ total amount subject to the cap, worked in pence and rounded half-up. The last section present gets the reduction minus the other shares.
- **Null limits.** A null or missing sum insured, vehicle value, single article limit or specified value means no cap at that step. `cap_gbp` comes out as `null`, with a warning.
- **Null excess.** A null excess that a rule calls for is taken as £0, with a warning. Escape of water does not fall back to the standard excess. For Motor, if only one of compulsory or voluntary is null, it counts as £0. The £1,000 subsidence excess is fixed.
- **One third of contents SI** is rounded half-up to the penny. If there is no contents SI, step 2 does not apply. Specified items count towards the limit (D-1).
- **`items_allowed_gbp`** is the section sum after steps 1 to 3 and before the section cap.
- **Excess total.** Each section's full excess is counted even when the settlement is £0 (G11).
- **`clauses_applied`** lists every clause that was applicable, whether or not it changed an amount. The order is H-3.2, H-2.2, H-4.1, M-3.1, H-1.2, M-1.2. The SPEC example shows only `["H-4.1"]`, and golden cases do not test this field, so the two implementations may disagree here.
- **Input rounding.** Input amounts become pence half-up from their shortest decimal form. All later steps are integer pence.
- **Output section order** is Buildings, Contents, Motor. Only sections that have items appear.
