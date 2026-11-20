import unittest
from collections import Counter
from common.io import ROOT,read_json
from project_a.cohort import comparison_cases, repeat_case


class ComparisonCohortTests(unittest.TestCase):
    def test_fixed_cohort_size_and_balance(self):
        cases = read_json(ROOT/'project_a/tests/fixtures/tax_cases.json')
        cohort = comparison_cases(cases)
        self.assertEqual(len(cohort),200)
        self.assertEqual(len({c['id'] for c in cohort}),200)
        self.assertEqual(Counter(c['input']['financial_year'] for c in cohort),{'2024-25':100,'2025-26':100})
        self.assertIn(repeat_case(cases)['id'],{c['id'] for c in cohort})
        self.assertEqual(len(comparison_cases(cases,10)),10)
