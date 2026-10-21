#!/usr/bin/env python3
"""Score every finished run against the dataset's answer key.

Usage (from the project root):  python3 scoring/score.py [--key PATH_TO_DATASET_SQLITE]
Reads runs/*/findings.json and runs/*/run.json; writes scoring/results.csv and scoring/detail/<run>.json.
The answer key is read from the ORIGINAL dataset (with its _truth_ tables), never from data/.
Settlement accuracy is checked against the calculator (tools/calculator/python), not the answer key.
"""
import argparse, csv, glob, json, os, re, sqlite3, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_KEY = os.path.join(os.path.dirname(ROOT), "046-study-data-sets", "datasets", "insurance_claims", "db", "insurance_claims.sqlite")
sys.path.insert(0, os.path.join(ROOT, "tools", "calculator", "python"))
sys.path.insert(0, os.path.join(ROOT, "tools", "calculator", "crosscheck"))

def load_key(path):
    c = sqlite3.connect(f"file:{path}?mode=ro&immutable=1", uri=True)
    cases = {}
    for cid, title, cls, rules in c.execute("select case_id, title, classification, rules_involved from _truth_cases"):
        cases[cid] = {"title": title, "genuine": cls.startswith("Genuine"),
                      "rules": set(re.findall(r"R-0\d", rules or "")), "claims": set()}
    # A case can be recorded against claims, or only against items, payments or complaints (e.g. duplicate invoices);
    # trace every record back to its claim so no case is unscoreable.
    for cid, rid in c.execute("""
            select r.case_id, coalesce(cl.claim_id, i.claim_id, p.claim_id, k.claim_id)
            from _truth_case_records r
            left join claims cl on r.table_name = 'claims' and cl.claim_id = r.record_id
            left join claim_items i on r.table_name = 'claim_items' and i.item_id = r.record_id
            left join claim_payments p on r.table_name = 'claim_payments' and p.payment_id = r.record_id
            left join complaints k on r.table_name = 'complaints' and k.complaint_id = r.record_id"""):
        if rid: cases[cid]["claims"].add(rid)
    for k, v in cases.items():
        if not v["claims"]: sys.exit(f"{k} has no claim it can be scored against")
    return cases

def calculator_settlements():
    from crosscheck import build_inputs
    from calc import calculate
    cases, _ = build_inputs()
    return {c["case_id"]: calculate(c)["settlement_total_gbp"] for c in cases}

def score(run_dir, key, calc):
    run = os.path.basename(run_dir.rstrip("/"))
    meta = json.load(open(os.path.join(run_dir, "run.json"))) if os.path.exists(os.path.join(run_dir, "run.json")) else {}
    findings = json.load(open(os.path.join(run_dir, "findings.json")))["findings"]
    flagged = {}
    for f in findings:
        for cl in [f["claim_id"]] + f.get("related_claim_ids", []):
            flagged.setdefault(cl, []).append(f)
    genuine = {k: v for k, v in key.items() if v["genuine"]}
    lookalike = {k: v for k, v in key.items() if not v["genuine"]}
    found = {k for k, v in genuine.items() if v["claims"] & flagged.keys()}
    right_reason = {k for k in found if any(set(f["rule_ids"]) & genuine[k]["rules"]
                                            for cl in genuine[k]["claims"] for f in flagged.get(cl, []))}
    false_flags = {k for k, v in lookalike.items() if v["claims"] & flagged.keys()}
    planted_claims = set().union(*(v["claims"] for v in key.values()))
    other = sorted(set(flagged) - planted_claims)
    # The calculator prices an accepted claim, so compare only limit and excess findings; a cover or decline
    # finding's "correct" settlement (often £0) is a judgement, reviewed by hand.
    settle = [f for f in findings if f.get("correct_settlement_gbp") is not None and f["claim_id"] in calc
              and f.get("family") in ("F2 Limits", "F3 Excess")]
    settle_ok = [f for f in settle if abs(f["correct_settlement_gbp"] - calc[f["claim_id"]]) <= 0.01]
    leaks = []
    log = os.path.join(run_dir, "log.jsonl")
    if os.path.exists(log):
        for line in open(log):
            # a run reading its own overflow files (paths with its own workspace slug) is fine; these patterns are
            # the answer key on the Mac, and the orchestrating session's own files in the cloud environment
            if any(w in line for w in ("046-study", "_truth_", "planted-cases", "expected-answers", "/scoring/", "projects/-home-claude/", "/tmp/claude-0/-home-claude/", "/mnt/user-data/")):
                leaks.append(json.loads(line).get("input"))
    row = {"run": run, "design": run.split("-")[0].upper(), "model": meta.get("model", ""),
           "genuine_found": len(found), "genuine_total": len(genuine), "right_reason": len(right_reason),
           "lookalikes_flagged": len(false_flags), "lookalikes_total": len(lookalike),
           "other_flags": len(other), "settlements_given": len(settle), "settlements_correct": len(settle_ok),
           "findings": len(findings), "answer_key_access": len(leaks)}
    detail = {"row": row, "found": sorted(found), "missed": sorted(set(genuine) - found),
              "wrong_reason": sorted(found - right_reason), "lookalikes_flagged": sorted(false_flags),
              "other_flags": other, "answer_key_access": leaks,
              "settlement_errors": [{"claim_id": f["claim_id"], "given": f["correct_settlement_gbp"], "calculator": calc[f["claim_id"]]}
                                    for f in settle if f not in settle_ok]}
    return row, detail

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--key", default=DEFAULT_KEY); a = ap.parse_args()
    key, calc = load_key(a.key), calculator_settlements()
    os.makedirs(os.path.join(ROOT, "scoring", "detail"), exist_ok=True)
    rows = []
    for d in sorted(glob.glob(os.path.join(ROOT, "runs", "*/"))):
        if not os.path.exists(os.path.join(d, "findings.json")): continue
        row, detail = score(d, key, calc); rows.append(row)
        json.dump(detail, open(os.path.join(ROOT, "scoring", "detail", row["run"] + ".json"), "w"), indent=2)
    if not rows: print("no finished runs"); return
    with open(os.path.join(ROOT, "scoring", "results.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)
    for r in rows: print(r)

if __name__ == "__main__":
    main()
