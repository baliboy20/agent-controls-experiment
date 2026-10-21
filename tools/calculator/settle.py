#!/usr/bin/env python3
"""Correct settlement for one claim, from the database, using the Python calculator.

Usage:  python3 tools/calculator/settle.py CLM-0007 [--db PATH]
Builds the calculator input from the claim's policy and its agreed items, then prints the calculator output.
Assumes the claim is accepted: cover, exclusions and evidence are separate checks.
"""
import argparse, json, os, re, sqlite3, sys
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(HERE, "python"))
from calc import calculate

def default_db():
    for p in (os.path.join(ROOT, "data", "claims.sqlite"), os.path.join(ROOT, "claims.sqlite")):
        if os.path.exists(p): return p
    sys.exit("claims.sqlite not found")

def specified(s):
    out = []
    for part in (s or "").split(";"):
        m = re.match(r"\s*(.+?),\s*£([\d,\.]+)\s*$", part)
        if m: out.append({"description": m.group(1), "value_gbp": float(m.group(2).replace(",", ""))})
    return out

def build_input(db, claim_id):
    c = sqlite3.connect(f"file:{db}?mode=ro&immutable=1", uri=True); c.row_factory = sqlite3.Row
    cl = c.execute("select * from claims where claim_id=?", (claim_id,)).fetchone()
    if not cl: sys.exit(f"{claim_id}: no such claim")
    p = c.execute("select * from policies where policy_id=?", (cl["policy_id"],)).fetchone()
    rows = c.execute("select * from claim_items where claim_id=? and agreed_amount_gbp is not null order by item_id", (claim_id,)).fetchall()
    if not rows: sys.exit(f"{claim_id}: no agreed items, nothing to calculate")
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
    return {"case_id": claim_id, "product": p["product"], "claim_type": cl["claim_type"], "policy": pol, "items": items}

if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("claim_id"); ap.add_argument("--db"); a = ap.parse_args()
    print(json.dumps(calculate(build_input(a.db or default_db(), a.claim_id)), indent=2))
