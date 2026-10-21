#!/usr/bin/env python3
"""Run both calculator implementations on every claim with agreed items and compare.

Usage (from the project root):  python3 tools/calculator/crosscheck/crosscheck.py
Writes tools/calculator/crosscheck/report.json. Exit code 0 when the implementations agree on every field.
Also lists claims where the recorded proposed settlement differs from the calculator (for information only).
"""
import json, os, re, sqlite3, subprocess, sys
HERE = os.path.dirname(os.path.abspath(__file__)); CALC = os.path.dirname(HERE); ROOT = os.path.dirname(os.path.dirname(CALC))
DB = os.path.join(ROOT, "data", "claims.sqlite")

def specified(s):
    out = []
    for part in (s or "").split(";"):
        m = re.match(r"\s*(.+?),\s*£([\d,\.]+)\s*$", part)
        if m: out.append({"description": m.group(1), "value_gbp": float(m.group(2).replace(",", ""))})
    return out

def build_inputs():
    c = sqlite3.connect(f"file:{DB}?mode=ro&immutable=1", uri=True); c.row_factory = sqlite3.Row
    cases, skipped = [], []
    for cl in c.execute("select * from claims order by claim_id"):
        p = c.execute("select * from policies where policy_id=?", (cl["policy_id"],)).fetchone()
        rows = c.execute("select * from claim_items where claim_id=? and agreed_amount_gbp is not null order by item_id", (cl["claim_id"],)).fetchall()
        if not rows: skipped.append(cl["claim_id"]); continue
        sp = specified(p["specified_items"]); items = []
        for it in rows:
            match = None
            if it["category"] == "Valuables":
                d = (it["description"] or "").lower()
                for x in sp:
                    if x["description"].lower() in d or d in x["description"].lower(): match = x["description"]
            items.append({"item_id": it["item_id"], "section": it["section"], "category": it["category"],
                          "agreed_amount_gbp": it["agreed_amount_gbp"], "specified_item": match})
        pol = {k: p[k] for k in ["buildings_sum_insured_gbp", "contents_sum_insured_gbp", "single_article_limit_gbp",
               "excess_standard_gbp", "excess_escape_of_water_gbp", "excess_compulsory_gbp", "excess_voluntary_gbp",
               "excess_windscreen_gbp", "vehicle_value_gbp"]}
        pol["specified_items"] = sp
        cases.append({"case_id": cl["claim_id"], "product": p["product"], "claim_type": cl["claim_type"],
                      "policy": pol, "items": items, "_recorded_settlement_gbp": cl["proposed_settlement_gbp"]})
    return cases, skipped

def main():
    cases, skipped = build_inputs()
    path = os.path.join(HERE, "inputs.json"); json.dump(cases, open(path, "w"), indent=1)
    py = {x["case_id"]: x for x in json.loads(subprocess.check_output([sys.executable, os.path.join(CALC, "python", "calc.py"), path]))}
    ts = {x["case_id"]: x for x in json.loads(subprocess.check_output(["node", os.path.join(CALC, "typescript", "calc.ts"), path]))}
    diffs = {}
    for k in py:
        a, b, d = py[k], ts[k], []
        for f in ["excess_total_gbp", "settlement_total_gbp"]:
            if abs((a[f] or 0) - (b[f] or 0)) > 0.005: d.append(f"{f}: py {a[f]} ts {b[f]}")
        for s in set(a["sections"]) | set(b["sections"]):
            for f in ["items_allowed_gbp", "cap_gbp", "capped_total_gbp", "excess_gbp", "settlement_gbp"]:
                u, v = a["sections"].get(s, {}).get(f), b["sections"].get(s, {}).get(f)
                if (u is None) != (v is None) or (u is not None and abs(u - v) > 0.005): d.append(f"{s}.{f}: py {u} ts {v}")
        if sorted(a["clauses_applied"]) != sorted(b["clauses_applied"]): d.append("clauses_applied differ")
        if d: diffs[k] = d
    recorded = [{"claim_id": c["case_id"], "recorded_gbp": c["_recorded_settlement_gbp"], "calculator_gbp": py[c["case_id"]]["settlement_total_gbp"]}
                for c in cases if c["_recorded_settlement_gbp"] is not None
                and abs(c["_recorded_settlement_gbp"] - py[c["case_id"]]["settlement_total_gbp"]) > 0.005]
    report = {"claims_compared": len(py), "skipped_no_agreed_items": skipped, "disagreements": diffs,
              "recorded_settlement_differs": recorded}
    json.dump(report, open(os.path.join(HERE, "report.json"), "w"), indent=2)
    print(f"compared {len(py)} claims; implementations disagree on {len(diffs)}; recorded settlement differs on {len(recorded)}")
    sys.exit(1 if diffs else 0)

if __name__ == "__main__":
    main()
