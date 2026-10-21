"""Settlement calculator (SPEC.md v0.3). Python 3.10+, standard library only.

calculate(case) -> dict in the SPEC.md output shape.
CLI: python3 calc.py input.json   (a single case object, a list of cases,
     or a golden-style {"cases": [...]} wrapper whose entries have "input").
"""
from __future__ import annotations

import json
import re
import sys
from decimal import Decimal, ROUND_HALF_UP
from typing import Any

CENT = Decimal("0.01")
ZERO = Decimal("0")
TRACE_AND_ACCESS_LIMIT = Decimal("5000")
SUBSIDENCE_EXCESS = Decimal("1000")
SECTION_ORDER = ("Buildings", "Contents", "Motor")
SECTION_LIMIT_FIELD = {
    "Buildings": "buildings_sum_insured_gbp",
    "Contents": "contents_sum_insured_gbp",
    "Motor": "vehicle_value_gbp",
}


def r2(x: Decimal) -> Decimal:
    """Round to 2dp, half up (step 7)."""
    return x.quantize(CENT, rounding=ROUND_HALF_UP)


def money(v: Any) -> Decimal | None:
    """Policy/item amount -> rounded Decimal, or None when missing/null (not applicable)."""
    if v is None:
        return None
    # str() avoids binary-float artefacts (e.g. 0.125 stays 0.125, 2.675 stays 2.675)
    return r2(Decimal(str(v)))


def out(d: Decimal | None) -> float | None:
    return None if d is None else float(r2(d))


def norm_description(s: str) -> str:
    """D-4: ignore case, leading/trailing spaces and repeated spaces."""
    return re.sub(r" {2,}", " ", s.strip(" ")).lower()


def parse_product(product: Any) -> str:
    """Step 0 / D-5: text before the first ' - ' must be Home or Motor."""
    if not isinstance(product, str):
        raise ValueError(f"product must be a string, got {product!r}")
    base = product.split(" - ", 1)[0]
    if base not in ("Home", "Motor"):
        raise ValueError(f"unknown product {product!r}: expected Home or Motor before ' - '")
    return base


def share_reduction(amounts: dict[str, Decimal], reduction: Decimal) -> dict[str, Decimal]:
    """D-3: split a claim-level reduction pro rata over sections' amounts subject to the cap.

    Each share is rounded half up; the last section (Buildings, Contents, Motor order)
    with an amount subject to the cap takes the rounding remainder.
    """
    total = sum(amounts.values(), ZERO)
    secs = [s for s in SECTION_ORDER if amounts.get(s, ZERO) > 0]
    shares = {s: ZERO for s in amounts}
    allocated = ZERO
    for s in secs[:-1]:
        shares[s] = r2(reduction * amounts[s] / total)
        allocated += shares[s]
    if secs:
        shares[secs[-1]] = r2(reduction - allocated)
    return shares


def calculate(case: dict) -> dict:
    # Accept either a bare input or a golden-style {"case_id", "input": {...}} record.
    inp = case["input"] if "input" in case and isinstance(case["input"], dict) else case
    case_id = case.get("case_id", inp.get("case_id"))
    claim_type = inp.get("claim_type")
    policy = inp.get("policy") or {}
    items = inp.get("items") or []

    # Step 0: product.
    product = parse_product(inp.get("product"))

    clauses: list[str] = []
    warnings: list[str] = []

    def clause(c: str) -> None:
        if c not in clauses:
            clauses.append(c)

    specified: dict[str, Decimal | None] = {}
    for s in policy.get("specified_items") or []:
        if s and s.get("description") is not None:
            specified.setdefault(norm_description(s["description"]), money(s.get("value_gbp")))

    single_article = money(policy.get("single_article_limit_gbp"))
    contents_si = money(policy.get("contents_sum_insured_gbp"))

    # Per-section subtotals after step 1.
    valuables: dict[str, Decimal] = {}
    trace: dict[str, Decimal] = {}
    other: dict[str, Decimal] = {}
    present: set[str] = set()
    has_valuables = has_trace = False

    for it in items:
        sec = it.get("section")
        if sec not in SECTION_LIMIT_FIELD:
            raise ValueError(f"{case_id}: unknown section {sec!r} on item {it.get('item_id')}")
        present.add(sec)
        amount = money(it.get("agreed_amount_gbp")) or ZERO
        cat = it.get("category")
        if cat == "Valuables":
            # Step 1: per-item valuables limit (H-3.2, D-4).
            has_valuables = True
            clause("H-3.2")
            name = it.get("specified_item")
            if name is not None and norm_description(name) in specified:
                limit = specified[norm_description(name)]
            else:
                if name is not None:
                    warnings.append(
                        f"{it.get('item_id')}: specified item {name!r} not found in policy; "
                        f"single article limit applied (H-3.2)"
                    )
                limit = single_article
            allowed = amount if limit is None else r2(min(amount, limit))
            if allowed < amount:
                warnings.append(
                    f"{it.get('item_id')}: valuable limited to {limit:.2f} per item (H-3.2)"
                )
            valuables[sec] = r2(valuables.get(sec, ZERO) + allowed)
        elif cat == "Trace and access" and claim_type == "Escape of water":
            has_trace = True
            trace[sec] = r2(trace.get(sec, ZERO) + amount)
        else:
            other[sec] = r2(other.get(sec, ZERO) + amount)

    # Step 2: valuables in total, per claim, limited to one third of contents SI (H-3.2, D-1, D-3).
    if has_valuables and contents_si is not None:
        third = r2(contents_si / Decimal(3))
        total = r2(sum(valuables.values(), ZERO))
        if total > third:
            warnings.append(
                f"valuables total {total:.2f} limited to one third of contents sum insured, "
                f"{third:.2f} (H-3.2)"
            )
            for sec, cut in share_reduction(valuables, r2(total - third)).items():
                valuables[sec] = r2(valuables[sec] - cut)

    # Step 3: trace and access, per claim, limited to £5,000 for escape of water (H-2.2, D-3).
    if has_trace:
        clause("H-2.2")
        total = r2(sum(trace.values(), ZERO))
        if total > TRACE_AND_ACCESS_LIMIT:
            warnings.append(
                f"trace and access total {total:.2f} limited to "
                f"{TRACE_AND_ACCESS_LIMIT:.2f} (H-2.2)"
            )
            for sec, cut in share_reduction(trace, r2(total - TRACE_AND_ACCESS_LIMIT)).items():
                trace[sec] = r2(trace[sec] - cut)

    sections_out: dict[str, dict] = {}
    excess_total = ZERO
    settlement_total = ZERO

    for sec in SECTION_ORDER:
        if sec not in present:
            continue
        items_allowed = r2(valuables.get(sec, ZERO) + trace.get(sec, ZERO) + other.get(sec, ZERO))

        # Step 4: section cap (H-4.1 / M-3.1). Null cap = not applicable (no cap).
        cap = money(policy.get(SECTION_LIMIT_FIELD[sec]))
        clause("M-3.1" if sec == "Motor" else "H-4.1")
        if cap is None:
            capped = items_allowed
            warnings.append(f"{sec}: no section limit in policy; total not capped")
        else:
            capped = r2(min(items_allowed, cap))

        # Step 5: excess (H-1.2 / M-1.2).
        excess = _excess(product, claim_type, sec, policy, clause, warnings)

        # Step 6: settlement.
        settlement = r2(max(ZERO, capped - excess))

        sections_out[sec] = {
            "items_allowed_gbp": out(items_allowed),
            "cap_gbp": out(cap),
            "capped_total_gbp": out(capped),
            "excess_gbp": out(excess),
            "settlement_gbp": out(settlement),
        }
        excess_total = r2(excess_total + excess)
        settlement_total = r2(settlement_total + settlement)

    return {
        "case_id": case_id,
        "sections": sections_out,
        "excess_total_gbp": out(excess_total),
        "settlement_total_gbp": out(settlement_total),
        "clauses_applied": clauses,
        "warnings": warnings,
    }


def _excess(product, claim_type, sec, policy, clause, warnings) -> Decimal:
    def amt(field: str) -> Decimal:
        v = money(policy.get(field))
        if v is None:
            warnings.append(f"{sec}: {field} not set; treated as not applicable (0)")
            return ZERO
        return v

    if product == "Motor":
        clause("M-1.2")
        if claim_type == "Windscreen - repair":
            return ZERO
        if claim_type == "Windscreen - replacement":
            return amt("excess_windscreen_gbp")
        return r2(amt("excess_compulsory_gbp") + amt("excess_voluntary_gbp"))
    clause("H-1.2")
    if claim_type == "Escape of water":
        return amt("excess_escape_of_water_gbp")
    if claim_type == "Subsidence":
        return SUBSIDENCE_EXCESS
    return amt("excess_standard_gbp")


def _load_cases(data: Any) -> list[dict] | dict:
    if isinstance(data, dict) and isinstance(data.get("cases"), list):
        return data["cases"]
    return data


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print("usage: python3 calc.py input.json", file=sys.stderr)
        return 2
    with open(argv[1], encoding="utf-8") as f:
        data = _load_cases(json.load(f))
    if isinstance(data, list):
        result: Any = [calculate(c) for c in data]
    else:
        result = calculate(data)
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
