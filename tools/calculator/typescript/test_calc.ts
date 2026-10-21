import { test, describe } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { calculate, normaliseCase, toPence, productOf } from "./calc.ts";
import type { Case } from "./calc.ts";

const TOL = 0.005;
const FIELDS = [
  "items_allowed_gbp",
  "cap_gbp",
  "capped_total_gbp",
  "excess_gbp",
  "settlement_gbp",
] as const;

function close(actual: unknown, expected: unknown, label: string): void {
  if (expected === null || actual === null) {
    assert.equal(actual, expected, label);
    return;
  }
  assert.equal(typeof actual, "number", `${label}: not a number`);
  assert.ok(
    Math.abs((actual as number) - (expected as number)) <= TOL,
    `${label}: expected ${expected}, got ${actual}`,
  );
}

const golden = JSON.parse(
  readFileSync(new URL("../golden/cases.json", import.meta.url), "utf8"),
);

describe("golden cases", () => {
  for (const gc of golden.cases) {
    test(`${gc.case_id}: ${gc.note}`, () => {
      const out = calculate(normaliseCase(gc));
      const exp = gc.expected;
      assert.equal(out.case_id, gc.case_id);
      assert.deepEqual(
        Object.keys(out.sections).sort(),
        Object.keys(exp.sections).sort(),
        "sections present",
      );
      for (const [sec, es] of Object.entries<any>(exp.sections)) {
        const os = (out.sections as any)[sec];
        for (const f of FIELDS) close(os[f], es[f], `${sec}.${f}`);
      }
      close(out.excess_total_gbp, exp.excess_total_gbp, "excess_total_gbp");
      close(out.settlement_total_gbp, exp.settlement_total_gbp, "settlement_total_gbp");
      assert.ok(Array.isArray(out.clauses_applied));
      assert.ok(Array.isArray(out.warnings));
    });
  }
});

function base(overrides: Partial<Case> = {}): Case {
  return {
    case_id: "X",
    product: "Home",
    claim_type: "Theft",
    policy: {
      buildings_sum_insured_gbp: null,
      contents_sum_insured_gbp: 30000,
      single_article_limit_gbp: 1000,
      specified_items: [],
      excess_standard_gbp: 100,
      excess_escape_of_water_gbp: null,
      excess_compulsory_gbp: null,
      excess_voluntary_gbp: null,
      excess_windscreen_gbp: null,
      vehicle_value_gbp: null,
    },
    items: [],
    ...overrides,
  };
}

describe("edge cases from the spec", () => {
  test("null policy amounts are not applicable, not zero cover", () => {
    const c = base({
      policy: { ...base().policy, contents_sum_insured_gbp: null, single_article_limit_gbp: null },
      items: [
        { item_id: "I1", section: "Contents", category: "Valuables", agreed_amount_gbp: 5000, specified_item: null },
        { item_id: "I2", section: "Contents", category: "Replacement", agreed_amount_gbp: 2000, specified_item: null },
      ],
    });
    const s = calculate(c).sections.Contents!;
    assert.equal(s.items_allowed_gbp, 7000); // no SAL, no one-third limit
    assert.equal(s.cap_gbp, null);
    assert.equal(s.capped_total_gbp, 7000); // no section cap
    assert.equal(s.settlement_gbp, 6900);
  });

  test("missing policy keys behave like nulls", () => {
    const c: Case = {
      case_id: "X",
      product: "Home",
      claim_type: "Fire",
      policy: { excess_standard_gbp: 50 },
      items: [{ item_id: "I1", section: "Buildings", category: "Repair", agreed_amount_gbp: 900, specified_item: null }],
    };
    const s = calculate(c).sections.Buildings!;
    assert.equal(s.cap_gbp, null);
    assert.equal(s.settlement_gbp, 850);
  });

  test("specified item not in schedule falls back to single article limit, with warning", () => {
    const c = base({
      policy: { ...base().policy, specified_items: [{ description: "Diamond ring", value_gbp: 5000 }] },
      items: [
        { item_id: "I1", section: "Contents", category: "Valuables", agreed_amount_gbp: 4000, specified_item: "Pearl necklace" },
      ],
    });
    const out = calculate(c);
    assert.equal(out.sections.Contents!.items_allowed_gbp, 1000);
    assert.ok(out.warnings.some((w) => w.includes("Pearl necklace")));
  });

  test("trace and access outside escape of water is not capped", () => {
    const c = base({
      claim_type: "Storm",
      policy: { ...base().policy, buildings_sum_insured_gbp: 300000 },
      items: [
        { item_id: "I1", section: "Buildings", category: "Trace and access", agreed_amount_gbp: 8000, specified_item: null },
      ],
    });
    const out = calculate(c);
    assert.equal(out.sections.Buildings!.items_allowed_gbp, 8000);
    assert.equal(out.sections.Buildings!.settlement_gbp, 7900);
    assert.ok(!out.clauses_applied.includes("H-2.2"));
  });

  test("one third of contents sum insured rounds half-up to the penny", () => {
    // 10000.00 / 3 = 3333.333... -> 3333.33 ; 200.00 / 3 = 66.666... -> 66.67
    const mk = (si: number) =>
      calculate(
        base({
          policy: { ...base().policy, contents_sum_insured_gbp: si, single_article_limit_gbp: null },
          items: [{ item_id: "I1", section: "Contents", category: "Valuables", agreed_amount_gbp: 99999, specified_item: null }],
        }),
      ).sections.Contents!.items_allowed_gbp;
    assert.equal(mk(10000), 3333.33);
    assert.equal(mk(200), 66.67);
  });

  test("input amounts are rounded half-up to 2dp without float error", () => {
    assert.equal(toPence(1.005), 101);
    assert.equal(toPence(2.675), 268);
    assert.equal(toPence(0.1 + 0.2), 30);
    assert.equal(toPence(1.004), 100);
    const out = calculate(
      base({
        items: [
          { item_id: "I1", section: "Contents", category: "Replacement", agreed_amount_gbp: 0.105, specified_item: null },
          { item_id: "I2", section: "Contents", category: "Replacement", agreed_amount_gbp: 0.205, specified_item: null },
          { item_id: "I3", section: "Contents", category: "Replacement", agreed_amount_gbp: 100.1, specified_item: null },
        ],
      }),
    );
    // 0.11 + 0.21 + 100.10 = 100.42 ; less 100 excess = 0.42
    assert.equal(out.sections.Contents!.items_allowed_gbp, 100.42);
    assert.equal(out.sections.Contents!.settlement_gbp, 0.42);
  });

  test("D-1: specified items count towards the one-third valuables limit", () => {
    const c = base({
      policy: {
        ...base().policy,
        contents_sum_insured_gbp: 12000,
        specified_items: [{ description: "Gold wristwatch", value_gbp: 7500 }],
      },
      items: [
        { item_id: "I1", section: "Contents", category: "Valuables", agreed_amount_gbp: 7000, specified_item: "Gold wristwatch" },
      ],
    });
    const out = calculate(c);
    assert.equal(out.sections.Contents!.items_allowed_gbp, 4000);
    assert.equal(out.sections.Contents!.settlement_gbp, 3900);
    assert.ok(out.warnings.some((w) => w.startsWith("H-3.2 valuables total limit")));
  });

  test("trace and access cap applies to aggregate, rest of section unaffected", () => {
    const c = base({
      claim_type: "Escape of water",
      policy: { ...base().policy, buildings_sum_insured_gbp: 300000, excess_escape_of_water_gbp: 250 },
      items: [
        { item_id: "I1", section: "Buildings", category: "Trace and access", agreed_amount_gbp: 3000, specified_item: null },
        { item_id: "I2", section: "Buildings", category: "Trace and access", agreed_amount_gbp: 3000, specified_item: null },
        { item_id: "I3", section: "Buildings", category: "Repair", agreed_amount_gbp: 500, specified_item: null },
      ],
    });
    const out = calculate(c);
    assert.equal(out.sections.Buildings!.items_allowed_gbp, 5500);
    assert.ok(out.warnings.some((w) => w.startsWith("H-2.2")));
  });

  test("D-2: cap before excess", () => {
    const c = base({
      claim_type: "Fire",
      policy: { ...base().policy, contents_sum_insured_gbp: 1000 },
      items: [{ item_id: "I1", section: "Contents", category: "Replacement", agreed_amount_gbp: 1500, specified_item: null }],
    });
    assert.equal(calculate(c).sections.Contents!.settlement_gbp, 900);
  });
});

describe("v0.3 rules (D-3, D-4, D-5)", () => {
  test("D-5: product is the text before the first ' - '", () => {
    assert.equal(productOf("Motor - Comprehensive"), "Motor");
    assert.equal(productOf("Home - Buildings and contents"), "Home");
    assert.equal(productOf("Home"), "Home");
    for (const bad of ["Travel", "home", "Motor-Comprehensive", "Motor Comprehensive", "", " Home"]) {
      assert.throws(() => productOf(bad), /Invalid product/, bad);
    }
    assert.throws(() => calculate(base({ product: "Pet - Gold" })), /Invalid product/);
  });

  test("D-5: a long Home product name still gets home excess rules", () => {
    const out = calculate(
      base({
        product: "Home - Premier",
        claim_type: "Subsidence",
        policy: { ...base().policy, buildings_sum_insured_gbp: 400000 },
        items: [{ item_id: "I1", section: "Buildings", category: "Repair", agreed_amount_gbp: 5000, specified_item: null }],
      }),
    );
    assert.equal(out.sections.Buildings!.excess_gbp, 1000);
  });

  test("D-4: specified item matching ignores case and spaces, but not other spelling", () => {
    const mk = (name: string) =>
      calculate(
        base({
          policy: { ...base().policy, specified_items: [{ description: " Gold   Wristwatch ", value_gbp: 5000 }] },
          items: [{ item_id: "I1", section: "Contents", category: "Valuables", agreed_amount_gbp: 4000, specified_item: name }],
        }),
      ).sections.Contents!.items_allowed_gbp;
    assert.equal(mk("gold wristwatch"), 4000);
    assert.equal(mk("  GOLD WRISTWATCH"), 4000);
    assert.equal(mk("Gold wrist watch"), 1000); // falls back to single article limit
  });

  test("D-3: pro-rata remainder goes to the last section in Buildings, Contents, Motor order", () => {
    // Contents item listed first, to show order comes from the section order, not the input.
    // Buildings T&A 2000.00, Contents T&A 4000.01 -> total 6000.01, reduction 1000.01.
    // Buildings share = 1000.01 * 2000 / 6000.01 = 333.3361... -> 333.34; Contents = 1000.01 - 333.34 = 666.67.
    const out = calculate(
      base({
        claim_type: "Escape of water",
        policy: { ...base().policy, buildings_sum_insured_gbp: 300000, excess_escape_of_water_gbp: 0 },
        items: [
          { item_id: "I1", section: "Contents", category: "Trace and access", agreed_amount_gbp: 4000.01, specified_item: null },
          { item_id: "I2", section: "Buildings", category: "Trace and access", agreed_amount_gbp: 2000, specified_item: null },
        ],
      }),
    );
    assert.equal(out.sections.Buildings!.items_allowed_gbp, 1666.66);
    assert.equal(out.sections.Contents!.items_allowed_gbp, 3333.34);
    assert.equal(out.settlement_total_gbp, 5000);
  });

  test("D-3: valuables one-third limit shared across sections per claim", () => {
    const out = calculate(
      base({
        policy: { ...base().policy, buildings_sum_insured_gbp: 300000, contents_sum_insured_gbp: 3000, single_article_limit_gbp: null, excess_standard_gbp: 0 },
        items: [
          { item_id: "I1", section: "Buildings", category: "Valuables", agreed_amount_gbp: 1000, specified_item: null },
          { item_id: "I2", section: "Contents", category: "Valuables", agreed_amount_gbp: 1000, specified_item: null },
        ],
      }),
    );
    // limit 1000, reduction 1000 shared 500/500
    assert.equal(out.sections.Buildings!.items_allowed_gbp, 500);
    assert.equal(out.sections.Contents!.items_allowed_gbp, 500);
  });
});
