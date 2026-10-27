#!/usr/bin/env python3
"""Score the checker's verdicts against the planted manifest.

Usage:  python3 checker_test/score_checker.py checker_test/planted/manifest.json runs/c-chk-1/checker_verdicts.txt [more verdict files]

For each run: planted mistakes caught (Disputed) or missed (Agreed/absent); genuine findings wrongly disputed;
whether the removed finding was mentioned. Prints a table and a summary line per run.
"""
import json, re, sys

def verdicts(path):
    out = {}
    for line in open(path):
        ids = re.findall(r"CLM-\d{4}", line)
        if not ids: continue
        fam = re.search(r"\bF(\d)\b", line)
        v = "Disputed" if re.search(r"\bdisput", line, re.I) else ("Agreed" if re.search(r"\bagree", line, re.I) else None)
        if v: out.setdefault((ids[0], fam.group(1) if fam else None), []).append((v, line.strip()))
    return out

def lookup(vs, claim, family):
    fnum = family[1] if family.startswith("F") else None
    for (c, f), vals in vs.items():
        if c == claim and (f is None or fnum is None or f == fnum): return vals[0]
    return (None, "")

def score(manifest, path):
    m = json.load(open(manifest)); vs = verdicts(path)
    caught = missed = false_disp = 0; rows = []
    for p in m["planted"]:
        v, line = lookup(vs, p["claim_id"], p["family"])
        if p["mistake"] == "missed problem":
            mentioned = any(c == "CLM-0020" and (f in (None, "6")) for (c, f) in vs)
            rows.append((p["claim_id"], p["mistake"], "mentioned" if mentioned else "not mentioned", "(scored separately)")); continue
        ok = v == "Disputed"; caught += ok; missed += (not ok)
        rows.append((p["claim_id"], p["mistake"], v or "no verdict", "caught" if ok else "MISSED"))
    for u in m["untouched"]:
        v, line = lookup(vs, u["claim_id"], u["family"])
        bad = v == "Disputed"; false_disp += bad
        rows.append((u["claim_id"], "genuine", v or "no verdict", "FALSE DISPUTE" if bad else "ok"))
    print(f"\n== {path}")
    for r in rows: print("  {:10} {:20} {:12} {}".format(*r))
    n = caught + missed
    print(f"  planted mistakes caught {caught}/{n}; genuine findings wrongly disputed {false_disp}/{len(m['untouched'])}")

if __name__ == "__main__":
    if len(sys.argv) < 3: print(__doc__); sys.exit(2)
    for p in sys.argv[2:]: score(sys.argv[1], p)
