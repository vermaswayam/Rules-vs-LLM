import unittest
from common.io import ROOT, read_json
from project_a.parser import parse_description


class ParserTests(unittest.TestCase):
    def test_conflicting_assessment_years_and_unquantified_claim(self):
        for text in [
            "Annual salary 12 lakh, AY 2025-26 and AY 2026-27, age 30, Indian resident, no deductions.",
            "Annual salary 12 lakh FY 2024-25 age 30 Indian resident 80C claimed, no other deductions.",
        ]:
            self.assertEqual(parse_description(text)["status"], "needs_clarification")

    def test_negating_one_income_head_does_not_hide_another(self):
        text = "Annual salary 12 lakh FY 2024-25 age 30 Indian resident, no capital gains but business income 2 lakh, no deductions."
        self.assertEqual(parse_description(text)["status"], "out_of_scope")

    def test_fifty_descriptions(self):
        cases = read_json(ROOT / "project_a/tests/fixtures/descriptions.json")
        self.assertEqual(len(cases), 50)
        for case in cases:
            with self.subTest(case=case["id"]):
                result = parse_description(case["text"])
                self.assertEqual(result["status"], case["expected_status"])
                for key, expected in case["expected_fields"].items():
                    self.assertEqual(result["fields"].get(key), expected)
                if result["status"] == "needs_clarification":
                    self.assertTrue(result["questions"])
