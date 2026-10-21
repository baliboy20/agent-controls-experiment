#!/usr/bin/env python3
"""Data controls for the claims database. Deterministic, read-only.

Usage:  python3 tools/controls/controls.py <command> [--db PATH]

  verify    File checksum and every table's row count against MANIFEST.json; no unexpected tables; no hot journal.
  totals    Control totals: claims, items and payments by count and value, by status, type and product.
  excess    R-03 reconciliation: excess deducted across a claim's payments against the excess recorded on the claim.
  invoices  R-05 screen: supplier items on different claims with the same supplier and either the same amount
            or overlapping service dates. A screen, not a verdict: each pair needs judgement.

Prints JSON. Exit code 0 = ran (verify: passed), 1 = verify failed, 2 = usage.
"""
import argparse, hashlib, json, os, sqlite3, sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def default_db():
    for p in (os.path.join(ROOT, "data", "claims.sqlite"), os.path.join(ROOT, "claims.sqlite")):
        if os.path.exists(p): return p
    sys.exit("claims.sqlite not found")

def connect(path):
    c = sqlite3.connect(f"file:{path}?mode=ro&immutable=1", uri=True); c.row_factory = sqlite3.Row; return c

def verify(path):
    m = json.load(open(os.path.join(os.path.dirname(path), "MANIFEST.json")))
    problems = []
    sha = hashlib.sha256(open(path, "rb").read()).hexdigest()
    if sha != m["sha256"]: problems.append(f"sha256 {sha} != manifest {m['sha256']}")
    j = path + "-journal"
    if os.path.exists(j) and os.path.getsize(j) > 0: problems.append("non-empty journal file next to the database")
    c = connect(path)
    tables = {n: c.execute(f'select count(*) from "{n}"').fetchone()[0] for (n,) in c.execute("select name from sqlite_master where type='table'")}
    for t, n in m["row_counts"].items():
        if tables.get(t) != n: problems.append(f"{t}: {tables.get(t)} rows, manifest {n}")
    problems += [f"unexpected table {t}" for t in tables if t not in m["row_counts"]]
    return {"check": "verify", "sha256": sha, "passed": not problems, "problems": problems}

def totals(path):
    c = connect(path); q = lambda s: [dict(r) for r in c.execute(s)]
    return {"check": "totals",
            "claims": q("select count(*) n, round(sum(claimed_amount_gbp),2) claimed_gbp, round(sum(proposed_settlement_gbp),2) proposed_gbp, round(sum(reserve_gbp),2) reserve_gbp from claims")[0],
            "claims_by_status": q("select claim_status, count(*) n from claims group by 1 order by 1"),
            "claims_by_product": q("select p.product, count(*) n, round(sum(c.claimed_amount_gbp),2) claimed_gbp from claims c join policies p using(policy_id) group by 1 order by 1"),
            "items": q("select count(*) n, round(sum(claimed_amount_gbp),2) claimed_gbp, round(sum(agreed_amount_gbp),2) agreed_gbp, sum(agreed_amount_gbp is null) not_agreed from claim_items")[0],
            "payments_by_type": q("select payment_type, direction, count(*) n, round(sum(gross_amount_gbp),2) gross_gbp, round(sum(excess_deducted_gbp),2) excess_gbp, round(sum(net_amount_gbp),2) net_gbp from claim_payments group by 1,2 order by 1"),
            "payments_net_check": q("select count(*) n_mismatched from claim_payments where abs(gross_amount_gbp - excess_deducted_gbp - net_amount_gbp) > 0.005")[0]}

def excess(path):
    c = connect(path)
    rows = [dict(r) for r in c.execute("""
        select c.claim_id, c.section, c.claim_type, c.excess_gbp recorded_excess_gbp,
               round(coalesce(sum(p.excess_deducted_gbp),0),2) deducted_gbp,
               sum(p.excess_deducted_gbp > 0) payments_with_excess
        from claims c left join claim_payments p on p.claim_id = c.claim_id
        group by c.claim_id order by c.claim_id""")]
    over = [r for r in rows if r["deducted_gbp"] - (r["recorded_excess_gbp"] or 0) > 0.005]
    multi = [r for r in rows if (r["payments_with_excess"] or 0) > 1]
    return {"check": "excess", "rule": "R-03", "claims_checked": len(rows),
            "deducted_exceeds_recorded": over, "excess_taken_from_more_than_one_payment": multi}

def invoices(path):
    c = connect(path)
    pairs = [dict(r) for r in c.execute("""
        select a.supplier_id, a.claim_id claim_a, a.item_id item_a, b.claim_id claim_b, b.item_id item_b,
               a.claimed_amount_gbp amount_a, b.claimed_amount_gbp amount_b,
               a.service_start start_a, a.service_end end_a, b.service_start start_b, b.service_end end_b,
               a.document_ref doc_a, b.document_ref doc_b,
               (abs(a.claimed_amount_gbp - b.claimed_amount_gbp) < 0.005) same_amount,
               (a.service_start is not null and b.service_start is not null
                and a.service_start <= coalesce(b.service_end, b.service_start)
                and b.service_start <= coalesce(a.service_end, a.service_start)) dates_overlap,
               (a.document_ref = b.document_ref) same_document
        from claim_items a join claim_items b
          on a.supplier_id = b.supplier_id and a.claim_id < b.claim_id
        where a.supplier_id is not null""")]
    hits = [p for p in pairs if p["same_amount"] or p["dates_overlap"] or p["same_document"]]
    return {"check": "invoices", "rule": "R-05", "pairs_screened": len(pairs), "pairs_to_review": hits}

if __name__ == "__main__":
    ap = argparse.ArgumentParser(add_help=False); ap.add_argument("command", nargs="?"); ap.add_argument("--db")
    a = ap.parse_args()
    fn = {"verify": verify, "totals": totals, "excess": excess, "invoices": invoices}.get(a.command)
    if not fn: print(__doc__); sys.exit(2)
    out = fn(a.db or default_db()); print(json.dumps(out, indent=2, default=str))
    sys.exit(1 if a.command == "verify" and not out["passed"] else 0)
