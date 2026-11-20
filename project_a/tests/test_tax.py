import unittest
from common.io import ROOT, read_json
from project_a.engine import calculate, compare
from project_a.models import TaxProfile


class TaxTests(unittest.TestCase):
    def test_frozen_expected_cases(self):
        cases = read_json(ROOT / "project_a/tests/fixtures/tax_cases.json")
        self.assertGreaterEqual(len(cases), 200)
        for case in cases:
            for regime in ["old", "new"]:
                with self.subTest(case=case["id"], regime=regime):
                    result = calculate(TaxProfile.from_dict(case["input"]), regime)
                    self.assertEqual(result["tax_payable"], case["expected"][regime])

    def test_manual_anchors(self):
        # Gross 12L, FY24 new: taxable 11.25L; 68,750 + 4% = 71,500.
        self.assertEqual(
            calculate(TaxProfile(1200000, "2024-25", 35, True), "new")["tax_payable"], 71500
        )
        self.assertEqual(
            calculate(TaxProfile(1275000, "2025-26", 35, True), "new")["tax_payable"], 0
        )
        # Rebate relief first, then cess, then section 288B rounding.
        self.assertEqual(
            calculate(TaxProfile(1275010, "2025-26", 35, True), "new")["tax_payable"], 10
        )

    def test_trace_reconciles(self):
        for salary in [400000, 1200000, 5050100, 10050100, 50050100]:
            for regime in ["old", "new"]:
                result = calculate(TaxProfile(salary, "2024-25", 35, True), regime)
                from decimal import Decimal

                total = sum(Decimal(line["amount"]) for line in result["tax_ledger"])
                self.assertEqual(total, result["tax_payable"])
                self.assertTrue(all(line["clause"] for line in result["tax_ledger"]))

    def test_rejects_unsupported_and_ambiguous(self):
        for fields in [
            {"salary": -1},
            {"salary": 1.5},
            {"salary": 1200000, "financial_year": "2026-27"},
            {"salary": 1200000, "capital_gains": 10},
            {"salary": 1200000, "home_interest": 1000},
        ]:
            with self.subTest(fields=fields), self.assertRaises((ValueError, TypeError)):
                TaxProfile.from_dict(
                    {"financial_year": "2024-25", "age": 35, "resident": True, **fields}
                )

    def test_nonresident_and_senior(self):
        self.assertGreater(
            calculate(TaxProfile(500000, "2024-25", 80, False), "old")["tax_payable"], 0
        )
        self.assertEqual(
            calculate(TaxProfile(550000, "2024-25", 80, True), "old")["tax_payable"], 0
        )

    def test_recommendation_tie(self):
        self.assertEqual(
            compare(TaxProfile(400000, "2024-25", 35, True))["recommendation"], "either"
        )

    def test_checkup_cap_not_wasted_on_already_full_bucket(self):
        profile = TaxProfile(
            1200000, "2024-25", 35, True, health_self=25000, checkup_self=4000, checkup_parents=4000
        )
        result = calculate(profile, "old")
        health = next(x for x in result["deductions"] if x["label"].startswith("80D"))
        self.assertEqual(health["amount"], "29000")

    def test_thirty_official_calculator_profiles(self):
        from scripts.verify_official import verify

        checks = verify()
        self.assertGreaterEqual(len(checks), 30)
        for check in checks:
            for regime in ["old", "new"]:
                with self.subTest(case=check["case_id"], regime=regime):
                    result = calculate(TaxProfile.from_dict(check["input"]), regime)
                    self.assertEqual(result["tax_payable"], check["official_" + regime])


if __name__ == "__main__":
    unittest.main()
