import json
import os
import unittest

from calc import calculate

HERE = os.path.dirname(os.path.abspath(__file__))
TOL = 0.005
FIELDS = ("items_allowed_gbp", "cap_gbp", "capped_total_gbp", "excess_gbp", "settlement_gbp")

with open(os.path.join(HERE, "..", "golden", "cases.json"), encoding="utf-8") as f:
    GOLDEN = json.load(f)["cases"]


def base_policy(**kw):
    p = {
        "buildings_sum_insured_gbp": None, "contents_sum_insured_gbp": None,
        "single_article_limit_gbp": None, "specified_items": [],
        "excess_standard_gbp": None, "excess_escape_of_water_gbp": None,
        "excess_compulsory_gbp": None, "excess_voluntary_gbp": None,
        "excess_windscreen_gbp": None, "vehicle_value_gbp": None,
    }
    p.update(kw)
    return p


def item(iid, section, category, amount, specified=None):
    return {"item_id": iid, "section": section, "category": category,
            "agreed_amount_gbp": amount, "specified_item": specified}


class GoldenCases(unittest.TestCase):
    def test_golden(self):
        for g in GOLDEN:
            with self.subTest(case=g["case_id"]):
                case = dict(g["input"], case_id=g["case_id"])
                got = calculate(case)
                exp = g["expected"]
                self.assertEqual(got["case_id"], g["case_id"])
                self.assertEqual(set(got["sections"]), set(exp["sections"]))
                for sec, fields in exp["sections"].items():
                    for k in FIELDS:
                        self.assertAlmostEqual(got["sections"][sec][k], fields[k], delta=TOL,
                                               msg=f"{g['case_id']} {sec}.{k}")
                for k in ("excess_total_gbp", "settlement_total_gbp"):
                    self.assertAlmostEqual(got[k], exp[k], delta=TOL, msg=f"{g['case_id']} {k}")
                self.assertEqual(set(got), {"case_id", "sections", "excess_total_gbp",
                                            "settlement_total_gbp", "clauses_applied", "warnings"})


class EdgeCases(unittest.TestCase):
    def test_null_cap_is_not_zero_cover(self):
        case = {"case_id": "E1", "product": "Home", "claim_type": "Storm",
                "policy": base_policy(excess_standard_gbp=100),
                "items": [item("I1", "Buildings", "Repair", 2000)]}
        r = calculate(case)
        b = r["sections"]["Buildings"]
        self.assertIsNone(b["cap_gbp"])
        self.assertEqual(b["capped_total_gbp"], 2000.0)
        self.assertEqual(b["settlement_gbp"], 1900.0)

    def test_null_single_article_limit_means_no_item_limit(self):
        case = {"case_id": "E2", "product": "Home", "claim_type": "Theft",
                "policy": base_policy(contents_sum_insured_gbp=60000, excess_standard_gbp=0),
                "items": [item("I1", "Contents", "Valuables", 5000)]}
        self.assertEqual(calculate(case)["sections"]["Contents"]["items_allowed_gbp"], 5000.0)

    def test_missing_specified_item_falls_back_to_single_article_limit(self):
        case = {"case_id": "E3", "product": "Home", "claim_type": "Theft",
                "policy": base_policy(contents_sum_insured_gbp=60000, single_article_limit_gbp=1500,
                                      specified_items=[{"description": "Gold watch", "value_gbp": 9000}],
                                      excess_standard_gbp=100),
                "items": [item("I1", "Contents", "Valuables", 4000, "Silver bracelet")]}
        r = calculate(case)
        self.assertEqual(r["sections"]["Contents"]["items_allowed_gbp"], 1500.0)
        self.assertTrue(any("not found" in w for w in r["warnings"]))

    def test_specified_items_count_towards_one_third(self):  # D-1
        case = {"case_id": "E4", "product": "Home", "claim_type": "Theft",
                "policy": base_policy(contents_sum_insured_gbp=15000, single_article_limit_gbp=1000,
                                      specified_items=[{"description": "Ring", "value_gbp": 8000}],
                                      excess_standard_gbp=100),
                "items": [item("I1", "Contents", "Valuables", 8000, "Ring"),
                          item("I2", "Contents", "Replacement", 500)]}
        r = calculate(case)
        self.assertEqual(r["sections"]["Contents"]["items_allowed_gbp"], 5500.0)
        self.assertTrue(any("one third" in w for w in r["warnings"]))

    def test_trace_and_access_not_capped_outside_escape_of_water(self):
        case = {"case_id": "E5", "product": "Home", "claim_type": "Storm",
                "policy": base_policy(buildings_sum_insured_gbp=300000, excess_standard_gbp=250),
                "items": [item("I1", "Buildings", "Trace and access", 7000)]}
        r = calculate(case)
        self.assertEqual(r["sections"]["Buildings"]["items_allowed_gbp"], 7000.0)
        self.assertNotIn("H-2.2", r["clauses_applied"])

    def test_trace_and_access_cap_warns(self):
        case = {"case_id": "E6", "product": "Home", "claim_type": "Escape of water",
                "policy": base_policy(buildings_sum_insured_gbp=300000, excess_escape_of_water_gbp=0),
                "items": [item("I1", "Buildings", "Trace and access", 3000),
                          item("I2", "Buildings", "Trace and access", 3000)]}
        r = calculate(case)
        self.assertEqual(r["sections"]["Buildings"]["items_allowed_gbp"], 5000.0)
        self.assertIn("H-2.2", r["clauses_applied"])
        self.assertTrue(any("trace and access" in w for w in r["warnings"]))

    def test_rounding_half_up_on_one_third(self):
        # 10000.05 / 3 = 3333.35 exactly -> 3333.35; 10000.04/3 = 3333.34666 -> 3333.35
        case = {"case_id": "E7", "product": "Home", "claim_type": "Theft",
                "policy": base_policy(contents_sum_insured_gbp=10000.04, excess_standard_gbp=0),
                "items": [item("I1", "Contents", "Valuables", 4000)]}
        self.assertEqual(calculate(case)["sections"]["Contents"]["items_allowed_gbp"], 3333.35)

    def test_rounding_half_up_on_amounts(self):
        # 0.125 and 2.675 must round half up (banker's / binary float would give 0.12 / 2.67)
        case = {"case_id": "E8", "product": "Home", "claim_type": "Storm",
                "policy": base_policy(excess_standard_gbp=0.125),
                "items": [item("I1", "Buildings", "Repair", 2.675)]}
        b = calculate(case)["sections"]["Buildings"]
        self.assertEqual(b["items_allowed_gbp"], 2.68)
        self.assertEqual(b["excess_gbp"], 0.13)
        self.assertEqual(b["settlement_gbp"], 2.55)

    def test_motor_null_voluntary_excess(self):
        case = {"case_id": "E9", "product": "Motor", "claim_type": "Theft",
                "policy": base_policy(excess_compulsory_gbp=300, vehicle_value_gbp=10000),
                "items": [item("I1", "Motor", "Repair", 2000)]}
        self.assertEqual(calculate(case)["sections"]["Motor"]["excess_gbp"], 300.0)

    # --- v0.3 rules ---

    def test_product_prefix_and_errors(self):  # step 0 / D-5
        base = {"case_id": "E10", "claim_type": "Theft",
                "policy": base_policy(excess_compulsory_gbp=300, excess_voluntary_gbp=50,
                                      vehicle_value_gbp=10000),
                "items": [item("I1", "Motor", "Repair", 2000)]}
        r = calculate(dict(base, product="Motor - Third party, fire and theft"))
        self.assertEqual(r["sections"]["Motor"]["excess_gbp"], 350.0)
        for bad in ("Travel", "Motor-Comprehensive", "motor", None, "Pet - Home"):
            with self.subTest(product=bad), self.assertRaises(ValueError):
                calculate(dict(base, product=bad))

    def test_specified_item_normalisation(self):  # D-4
        case = {"case_id": "E11", "product": "Home", "claim_type": "Theft",
                "policy": base_policy(contents_sum_insured_gbp=60000, single_article_limit_gbp=1000,
                                      specified_items=[{"description": " Gold   Watch ", "value_gbp": 5000}],
                                      excess_standard_gbp=0),
                "items": [item("I1", "Contents", "Valuables", 4000, "gold watch"),
                          item("I2", "Contents", "Valuables", 4000, "goldwatch")]}
        r = calculate(case)
        # I1 matches (5000 limit -> 4000); I2 does not (spaces inside words are not ignored) -> 1000
        self.assertEqual(r["sections"]["Contents"]["items_allowed_gbp"], 5000.0)

    def test_trace_and_access_pro_rata_rounding_remainder(self):  # D-3
        # T&A 1000 + 1000 + 4000.01 -> 6000.01, reduction 1000.01 split by 1000 : 5000.01
        # Buildings share = 1000.01*1000/6000.01 = 166.6680... -> 166.67; Contents takes 833.34
        case = {"case_id": "E12", "product": "Home", "claim_type": "Escape of water",
                "policy": base_policy(buildings_sum_insured_gbp=300000, contents_sum_insured_gbp=50000,
                                      excess_escape_of_water_gbp=0),
                "items": [item("I1", "Buildings", "Trace and access", 1000),
                          item("I2", "Contents", "Trace and access", 1000),
                          item("I3", "Contents", "Trace and access", 4000.01)]}
        r = calculate(case)
        b = r["sections"]["Buildings"]["items_allowed_gbp"]
        c = r["sections"]["Contents"]["items_allowed_gbp"]
        self.assertEqual(b, 833.33)
        self.assertEqual(c, 4166.67)
        self.assertAlmostEqual(b + c, 5000.0, places=6)

    def test_valuables_one_third_per_claim_across_sections(self):  # D-3
        # Valuables recorded under Buildings and Contents; one third of 9000 = 3000 claim-wide.
        case = {"case_id": "E13", "product": "Home", "claim_type": "Theft",
                "policy": base_policy(buildings_sum_insured_gbp=200000, contents_sum_insured_gbp=9000,
                                      excess_standard_gbp=0),
                "items": [item("I1", "Buildings", "Valuables", 1000),
                          item("I2", "Contents", "Valuables", 3000)]}
        r = calculate(case)
        self.assertEqual(r["sections"]["Buildings"]["items_allowed_gbp"], 750.0)
        self.assertEqual(r["sections"]["Contents"]["items_allowed_gbp"], 2250.0)
        self.assertEqual(sum(1 for w in r["warnings"] if "one third" in w), 1)

    def test_list_input_via_cli(self):
        import subprocess, sys, tempfile
        cases = [dict(g["input"], case_id=g["case_id"]) for g in GOLDEN[:2]]
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
            json.dump(cases, f)
        try:
            outp = subprocess.run([sys.executable, os.path.join(HERE, "calc.py"), f.name],
                                  capture_output=True, text=True, check=True).stdout
        finally:
            os.unlink(f.name)
        res = json.loads(outp)
        self.assertEqual([r["case_id"] for r in res], ["G01", "G02"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
