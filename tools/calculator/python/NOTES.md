# Spec ambiguities and how calc.py reads them (SPEC.md v0.3)

## Resolved by v0.3 (D-3 to D-5)
- **The valuables and trace-and-access caps are per claim (D-3).** This replaces my v0.2 per-section reading. The reduction is shared pro rata, in proportion to each section's amount subject to that cap. For valuables that is the allowed valuables after step 1; for trace and access it is the agreed amounts. Each share is rounded half up. The last section, in Buildings, Contents, Motor order, takes the rounding remainder. Each cap gives one claim-level warning.
- **Specified item matching (D-4).** Strip leading and trailing spaces, collapse runs of spaces, lower-case, then compare exactly.
- **Product (D-5).** The text before the first `" - "` must be exactly `Home` or `Motor`, otherwise `ValueError`. A missing product is also an error. The old fallback to the section name has been removed.

## Still my reading
- **"Last section" in the D-3 remainder rule.** I take it to mean the last section that has a positive amount subject to the cap. A section with nothing under that cap gets a share of 0, never the remainder.
- **Matching is case-sensitive (D-5).** `Home`/`Motor` must match exactly, so `"motor"` and `"Motor-Comprehensive"` (no spaces round the dash) are errors. Spaces round the prefix are not trimmed.
- **Only spaces are normalised (D-4).** Tabs and other whitespace are left as they are, and spaces *inside* words are not removed. `"goldwatch"` does not match `"Gold Watch"`. I use `str.lower()` rather than `casefold()` to match JavaScript's `toLowerCase()`. If two schedule entries normalise to the same text, the first one wins.
- **Null section limit (step 4).** "Not applicable, never zero cover" means no cap. `cap_gbp` is output as `null`, `capped_total_gbp` = `items_allowed_gbp`, and a warning is added.
- **Null single article limit or specified value (step 1).** No per-item limit. A null contents sum insured means no one-third limit (step 2).
- **Null excess amounts (step 5).** Counted as £0, with a warning. For Motor "compulsory + voluntary", a null part counts as 0.
- **Missing specified item.** If `specified_item` is given but doesn't match, the item falls back to the single article limit, with a warning.
- **A specified item's limit replaces the single article limit** (G05 confirms this).
- **Excess on a section with £0 allowed.** The excess is still charged ("every Home section claimed carries its own excess") and the settlement floors at 0. So `excess_total_gbp` can be larger than the excess actually absorbed (G11).
- **Warnings.** Steps 2 and 3 are required to warn. I also warn on per-item valuables reductions, a specified item that isn't found, and null limits or excesses. The wording is free-form.
- **`clauses_applied`.** I list every clause whose rule was used, in order of first use: H-3.2 (when Valuables are present), H-2.2 (escape of water with trace and access), H-4.1/M-3.1, H-1.2/M-1.2. Golden cases don't check this field, so the Python and TypeScript implementations may differ here.
- **Rounding.** Every input amount is rounded to 2dp half-up when read, using `Decimal(str(x))`. Rounding is also applied after every sum, min, division, share and subtraction.
- **Unknown section.** Raises `ValueError`.
