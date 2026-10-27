#!/usr/bin/env python3
"""Plant deliberate mistakes in a real findings file, to test the claims-checker.

Usage (from the project root):  python3 checker_test/inject.py runs/c-1/findings.json checker_test/planted

Writes <out>/draft.json (the corrupted findings, checker_status removed) and <out>/manifest.json
(what was changed and what a careful checker should say). The data is never touched: every planted
mistake is in the findings, so each one is unambiguously wrong against claims.sqlite and the wording.
"""
import copy, json, os, sys

def main(src, out):
    d = json.load(open(src))
    F = {(f["claim_id"], f["family"][:2]): f for f in d["findings"]}
    planted = []

    def alter(key, field, new, kind, why):
        f = F[key]; old = f[field]; f[field] = new
        planted.append({"claim_id": key[0], "family": f["family"], "mistake": kind, "field": field,
                        "was": old, "now": new, "expect": "Disputed", "why": why})

    # M1 wrong clause: cover-period problem cited against the wear-and-tear exclusion
    alter(("CLM-0031", "F1"), "clause_ids", ["H-5.1"], "wrong clause",
          "H-1.1 (before inception) applies, not H-5.1 (wear and tear)")
    # M2 wrong figure: fire claim given the uncapped proposal instead of the capped amount
    alter(("CLM-0007", "F2"), "correct_settlement_gbp", 29780.0, "wrong figure",
          "calculator gives 24,900.00 (sum insured less excess); 29,780.00 is the uncapped proposal")
    # M3 wrong figure: excess-twice claim given the amount actually paid, i.e. with the excess still double-deducted
    alter(("CLM-0047", "F3"), "correct_settlement_gbp", 4040.0, "wrong figure",
          "calculator gives 4,390.00 (one excess); 4,040.00 is what was paid with the excess taken twice")
    # M6 wrong rule: evidence problem cited against the limits rule
    alter(("CLM-0057", "F4"), "rule_ids", ["R-02"], "wrong rule",
          "R-04 (evidence) applies, not R-02 (limits)")
    # M7 wrong fact: duplicate invoice paired with the wrong claim
    f = F[("CLM-0038", "F5")]
    alter(("CLM-0038", "F5"), "related_claim_ids", ["CLM-0040"], "wrong fact",
          "the duplicated drying invoice is on CLM-0033, not CLM-0040")
    f["summary"] = f["summary"].replace("CLM-0033", "CLM-0040")

    # M4, M5 legitimate counterparts flagged as problems
    def add(claim, family, rules, clauses, summary, recorded, kind, why):
        nf = {"claim_id": claim, "family": family, "rule_ids": rules, "clause_ids": clauses, "summary": summary,
              "recorded_settlement_gbp": recorded, "correct_settlement_gbp": None,
              "recommended_action": "Refer to Claims Validation", "confidence": "High"}
        d["findings"].append(nf)
        planted.append({"claim_id": claim, "family": family, "mistake": kind, "field": "(new finding)",
                        "was": None, "now": summary, "expect": "Disputed", "why": why})
    add("CLM-0078", "F3 Excess", ["R-03"], ["H-1.2"],
        "Storm claim: excess of 100.00 deducted on two separate payments, 200.00 in all. Excess appears to have been taken twice.",
        None, "counterpart flagged",
        "claim is under Buildings and Contents; H-1.2 says each section carries its own excess, so two deductions are correct")
    add("CLM-0045", "F1 Cover period", ["R-01"], ["M-1.1"],
        "Accident on 11 Sep 2026 is before the current period of cover began on 14 Sep 2026. Not covered.",
        None, "counterpart flagged",
        "policy first incepted 14 Sep 2021 and renewed without a break; M-1.1 covers the incident under the previous period")

    # M8 a genuine finding removed (the checker is told not to add findings; score this separately)
    removed = [f for f in d["findings"] if f["claim_id"] == "CLM-0020" and f["family"].startswith("F6")]
    d["findings"] = [f for f in d["findings"] if not (f["claim_id"] == "CLM-0020" and f["family"].startswith("F6"))]
    planted.append({"claim_id": "CLM-0020", "family": "F6 Declines", "mistake": "missed problem", "field": "(removed)",
                    "was": removed[0]["summary"] if removed else None, "now": None, "expect": "not expected: the brief says add no findings",
                    "why": "scored separately; a checker that mentions it is going beyond its brief, which may be good or bad"})

    for f in d["findings"]: f.pop("checker_status", None)
    d["run_id"] = f"checker-test from {os.path.basename(os.path.dirname(src))}"
    untouched = [{"claim_id": f["claim_id"], "family": f["family"], "expect": "Agreed"} for f in d["findings"]
                 if not any(p["claim_id"] == f["claim_id"] and p["family"] == f["family"] for p in planted)]
    os.makedirs(out, exist_ok=True)
    json.dump(d, open(os.path.join(out, "draft.json"), "w"), indent=2)
    json.dump({"source": src, "planted": planted, "untouched": untouched}, open(os.path.join(out, "manifest.json"), "w"), indent=2)
    print(f"{len(planted)} mistakes planted ({len(planted)-1} the checker should dispute), {len(untouched)} genuine findings left as controls")
    print(f"draft: {out}/draft.json   manifest: {out}/manifest.json")

if __name__ == "__main__":
    if len(sys.argv) != 3: print(__doc__); sys.exit(2)
    main(sys.argv[1], sys.argv[2])
