// Settlement calculator, TypeScript implementation of SPEC.md v0.3.
// All money is held as integer pence. Inputs are converted to pence with
// half-up rounding to 2dp; every derived amount is rounded half-up to pence.
// Runs under plain Node 22 type stripping: `node calc.ts input.json`.

import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";

type Section = "Buildings" | "Contents" | "Motor";
const SECTION_ORDER: Section[] = ["Buildings", "Contents", "Motor"];

const TRACE_AND_ACCESS_LIMIT_P = 500000; // £5,000
const SUBSIDENCE_EXCESS_P = 100000; // £1,000

export interface SpecifiedItem {
  description: string;
  value_gbp: number | null;
}

export interface Policy {
  buildings_sum_insured_gbp?: number | null;
  contents_sum_insured_gbp?: number | null;
  single_article_limit_gbp?: number | null;
  specified_items?: SpecifiedItem[] | null;
  excess_standard_gbp?: number | null;
  excess_escape_of_water_gbp?: number | null;
  excess_compulsory_gbp?: number | null;
  excess_voluntary_gbp?: number | null;
  excess_windscreen_gbp?: number | null;
  vehicle_value_gbp?: number | null;
}

export interface Item {
  item_id: string;
  section: Section;
  category: string;
  agreed_amount_gbp: number;
  specified_item?: string | null;
}

export interface Case {
  case_id?: string;
  product: string; // "Home", "Motor", or e.g. "Motor - Comprehensive" (D-5)
  claim_type: string;
  policy: Policy;
  items: Item[];
}

export interface SectionResult {
  items_allowed_gbp: number;
  cap_gbp: number | null;
  capped_total_gbp: number;
  excess_gbp: number;
  settlement_gbp: number;
}

export interface Result {
  case_id: string | null;
  sections: Partial<Record<Section, SectionResult>>;
  excess_total_gbp: number;
  settlement_total_gbp: number;
  clauses_applied: string[];
  warnings: string[];
}

// ---------- money helpers (integer pence) ----------

/**
 * Convert a GBP amount to integer pence, rounding half-up (away from zero for
 * the magnitude) at 2dp. Works from the shortest decimal representation of the
 * number so that 1.005 is treated as 1.005, not 1.00499999...
 */
export function toPence(gbp: number): number {
  if (!Number.isFinite(gbp)) throw new Error(`Invalid money amount: ${gbp}`);
  const neg = gbp < 0;
  let s = String(Math.abs(gbp));
  if (/e/i.test(s)) s = Math.abs(gbp).toFixed(20).replace(/0+$/, "");
  const [intPart, fracRaw = ""] = s.split(".");
  const frac = (fracRaw + "000").slice(0, 3);
  let pence = Number(intPart) * 100 + Number(frac.slice(0, 2));
  if (Number(frac[2]) >= 5) pence += 1;
  return neg ? -pence : pence;
}

export function toGbp(pence: number): number {
  return pence / 100;
}

function fmt(pence: number): string {
  const sign = pence < 0 ? "-" : "";
  const a = Math.abs(pence);
  return `${sign}£${Math.floor(a / 100)}.${String(a % 100).padStart(2, "0")}`;
}

/** Half-up rounding of a non-negative integer division to integer pence. */
function divHalfUp(numerator: number, denominator: number): number {
  return Math.floor((2 * numerator + denominator) / (2 * denominator));
}

/** Null/undefined policy amounts mean "not applicable". */
function optPence(v: number | null | undefined): number | null {
  return v === null || v === undefined ? null : toPence(v);
}

/**
 * Share an aggregate reduction between sections (D-3): in proportion to each
 * section's amount subject to the cap, each share rounded half up, with the
 * last section in the order Buildings, Contents, Motor taking the remainder.
 */
function allocateReduction(
  bySection: Map<Section, number>,
  reduction: number,
): Map<Section, number> {
  const out = new Map<Section, number>();
  const entries = SECTION_ORDER.filter((s) => bySection.has(s)).map(
    (s) => [s, bySection.get(s)!] as [Section, number],
  );
  const total = entries.reduce((a, [, v]) => a + v, 0);
  let remaining = reduction;
  entries.forEach(([sec, v], idx) => {
    const share =
      idx === entries.length - 1 ? remaining : divHalfUp(reduction * v, total);
    remaining -= share;
    out.set(sec, share);
  });
  return out;
}

// ---------- calculator ----------

/** Step 0 (D-5): product is the text before the first " - "; must be Home or Motor. */
export function productOf(product: unknown): "Home" | "Motor" {
  if (typeof product !== "string") {
    throw new Error(`Invalid product: ${JSON.stringify(product)}`);
  }
  const i = product.indexOf(" - ");
  const head = i === -1 ? product : product.slice(0, i);
  if (head === "Home" || head === "Motor") return head;
  throw new Error(`Invalid product: ${JSON.stringify(product)} (must start with "Home" or "Motor")`);
}

/** D-4: compare ignoring case, leading/trailing spaces and repeated spaces. */
export function normaliseDescription(s: string): string {
  return s.replace(/^ +| +$/g, "").replace(/ {2,}/g, " ").toLowerCase();
}

export function calculate(c: Case): Result {
  const product = productOf(c.product);
  const policy: Policy = c.policy ?? {};
  const items: Item[] = c.items ?? [];
  const clauses = new Set<string>();
  const warnings: string[] = [];

  // Allowed pence per item (after step 1), plus section totals.
  const allowed = new Map<Item, number>();
  for (const it of items) allowed.set(it, toPence(it.agreed_amount_gbp));

  // Step 1: Valuables, per item (H-3.2).
  const sal = optPence(policy.single_article_limit_gbp);
  const specified = policy.specified_items ?? [];
  const valuables = items.filter((it) => it.category === "Valuables");
  for (const it of valuables) {
    clauses.add("H-3.2");
    let limit: number | null = null;
    const name = it.specified_item;
    const entry =
      name !== null && name !== undefined
        ? specified.find(
            (s) =>
              typeof s.description === "string" &&
              normaliseDescription(s.description) === normaliseDescription(name),
          )
        : undefined;
    if (entry && entry.value_gbp !== null && entry.value_gbp !== undefined) {
      limit = toPence(entry.value_gbp);
    } else {
      if (name !== null && name !== undefined) {
        warnings.push(
          `H-3.2: item ${it.item_id} names specified item "${name}" which is not in the policy schedule; single article limit applied`,
        );
      }
      limit = sal;
    }
    const a = allowed.get(it)!;
    if (limit !== null && a > limit) allowed.set(it, limit);
  }

  // Section subtotals after step 1 (bucketed so steps 2-3 can reduce aggregates).
  const subtotal = (pred: (it: Item) => boolean): Map<Section, number> => {
    const m = new Map<Section, number>();
    for (const it of items)
      if (pred(it)) m.set(it.section, (m.get(it.section) ?? 0) + allowed.get(it)!);
    return m;
  };
  const sectionReduction = new Map<Section, number>();
  const addReduction = (m: Map<Section, number>) => {
    for (const [s, r] of m) sectionReduction.set(s, (sectionReduction.get(s) ?? 0) + r);
  };

  // Step 2: Valuables in total, one third of contents sum insured (H-3.2, D-1).
  const contentsSi = optPence(policy.contents_sum_insured_gbp);
  if (valuables.length > 0 && contentsSi !== null) {
    const limit = divHalfUp(contentsSi, 3);
    const bySec = subtotal((it) => it.category === "Valuables");
    const total = [...bySec.values()].reduce((a, b) => a + b, 0);
    if (total > limit) {
      addReduction(allocateReduction(bySec, total - limit));
      warnings.push(
        `H-3.2 valuables total limit: allowed valuables ${fmt(total)} reduced to ${fmt(limit)} (one third of contents sum insured)`,
      );
    }
  }

  // Step 3: Trace and access, escape of water only (H-2.2).
  if (c.claim_type === "Escape of water") {
    const ta = items.filter((it) => it.category === "Trace and access");
    if (ta.length > 0) {
      clauses.add("H-2.2");
      const bySec = subtotal((it) => it.category === "Trace and access");
      const total = [...bySec.values()].reduce((a, b) => a + b, 0);
      if (total > TRACE_AND_ACCESS_LIMIT_P) {
        addReduction(allocateReduction(bySec, total - TRACE_AND_ACCESS_LIMIT_P));
        warnings.push(
          `H-2.2 trace and access limit: ${fmt(total)} reduced to ${fmt(TRACE_AND_ACCESS_LIMIT_P)}`,
        );
      }
    }
  }

  // Steps 4-6 per section.
  const present = SECTION_ORDER.filter((s) => items.some((it) => it.section === s));
  const sections: Partial<Record<Section, SectionResult>> = {};
  let excessTotal = 0;
  let settlementTotal = 0;

  for (const sec of present) {
    // Step 4: section total and cap (H-4.1 / M-3.1).
    let itemsAllowed = 0;
    for (const it of items) if (it.section === sec) itemsAllowed += allowed.get(it)!;
    itemsAllowed -= sectionReduction.get(sec) ?? 0;

    const capClause = sec === "Motor" ? "M-3.1" : "H-4.1";
    clauses.add(capClause);
    const cap =
      sec === "Buildings"
        ? optPence(policy.buildings_sum_insured_gbp)
        : sec === "Contents"
          ? contentsSi
          : optPence(policy.vehicle_value_gbp);
    if (cap === null) {
      warnings.push(`${capClause}: no limit for ${sec} on the policy; section not capped`);
    }
    const capped = cap !== null && itemsAllowed > cap ? cap : itemsAllowed;

    // Step 5: excess (H-1.2 / M-1.2).
    const excess = excessFor(product, c.claim_type, sec, policy, warnings, clauses);

    // Step 6: settlement.
    const settlement = Math.max(0, capped - excess);

    sections[sec] = {
      items_allowed_gbp: toGbp(itemsAllowed),
      cap_gbp: cap === null ? null : toGbp(cap),
      capped_total_gbp: toGbp(capped),
      excess_gbp: toGbp(excess),
      settlement_gbp: toGbp(settlement),
    };
    excessTotal += excess;
    settlementTotal += settlement;
  }

  const order = ["H-3.2", "H-2.2", "H-4.1", "M-3.1", "H-1.2", "M-1.2"];
  return {
    case_id: c.case_id ?? null,
    sections,
    excess_total_gbp: toGbp(excessTotal),
    settlement_total_gbp: toGbp(settlementTotal),
    clauses_applied: order.filter((k) => clauses.has(k)),
    warnings,
  };
}

function excessFor(
  product: "Home" | "Motor",
  claimType: string,
  sec: Section,
  policy: Policy,
  warnings: string[],
  clauses: Set<string>,
): number {
  const na = (label: string, v: number | null): number => {
    if (v === null) {
      warnings.push(`${label} not on the policy; treated as not applicable (£0.00) for ${sec}`);
      return 0;
    }
    return v;
  };
  if (product === "Motor") {
    clauses.add("M-1.2");
    switch (claimType) {
      case "Windscreen - repair":
        return 0;
      case "Windscreen - replacement":
        return na("Windscreen excess", optPence(policy.excess_windscreen_gbp));
      default: {
        const comp = optPence(policy.excess_compulsory_gbp);
        const vol = optPence(policy.excess_voluntary_gbp);
        if (comp === null && vol === null) {
          return na("Compulsory and voluntary excess", null);
        }
        return (comp ?? 0) + (vol ?? 0);
      }
    }
  }
  clauses.add("H-1.2");
  switch (claimType) {
    case "Escape of water":
      return na("Escape of water excess", optPence(policy.excess_escape_of_water_gbp));
    case "Subsidence":
      return SUBSIDENCE_EXCESS_P;
    default:
      return na("Standard excess", optPence(policy.excess_standard_gbp));
  }
}

/** Accept a bare case, a golden-style wrapper {case_id, input}, or {cases: [...]}. */
export function normaliseCase(raw: any): Case {
  if (raw && typeof raw === "object" && raw.input && typeof raw.input === "object") {
    return { ...raw.input, case_id: raw.input.case_id ?? raw.case_id };
  }
  return raw as Case;
}

function main(argv: string[]): void {
  const path = argv[2];
  if (!path) {
    process.stderr.write("usage: node calc.ts input.json\n");
    process.exit(2);
  }
  const data = JSON.parse(readFileSync(path, "utf8"));
  const list = Array.isArray(data) ? data : Array.isArray(data?.cases) ? data.cases : null;
  let failed = false;
  const run = (x: any) => {
    const c = normaliseCase(x);
    try {
      return calculate(c);
    } catch (e) {
      failed = true;
      return { case_id: c?.case_id ?? null, error: (e as Error).message };
    }
  };
  const out = list ? list.map(run) : run(data);
  process.stdout.write(JSON.stringify(out, null, 2) + "\n");
  if (failed) process.exitCode = 1;
}

if (process.argv[1] && fileURLToPath(import.meta.url) === process.argv[1]) {
  main(process.argv);
}
