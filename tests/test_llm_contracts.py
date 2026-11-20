import unittest
from project_a.compiled import acceptance, load_policy, validate_policy
from project_a.policy import hand_policy
from project_a.models import TaxProfile
from project_a.llm_query import calculate_with_llm
from project_b.llm_review import review_with_llm
from project_b.reference import Reference
from project_b.tests.test_pipeline import sample_rows
from project_b.benchmark import measured_review


class FakeClient:
    """Contract-test stub only. Never used by benchmarks or result generation."""

    def __init__(self, response):
        self.response = response

    def generate(self, *args, **kwargs):
        return {"response": self.response}


class ModelContracts(unittest.TestCase):
    def test_all_compiled_fixture_answers(self):
        for year in ["2024-25", "2025-26"]:
            self.assertEqual(acceptance(load_policy(year), year), [])

    def test_wrong_compilation_is_rejected(self):
        candidate = hand_policy("2025-26")
        candidate["rebate_new_threshold"] = 700000
        self.assertTrue(acceptance(candidate, "2025-26"))
        candidate["injected_python"] = '__import__("os")'
        with self.assertRaises(ValueError):
            validate_policy(candidate, "2025-26")

    def test_invalid_rates_fail_closed(self):
        for field, value in [
            ("cess", "NaN"),
            ("cess", '__import__("os")'),
            ("surcharge_new", [[1, "Infinity"]]),
            ("new_slabs", [[None, "-0.1"]]),
        ]:
            candidate = hand_policy("2025-26")
            candidate[field] = value
            with self.subTest(field=field, value=value), self.assertRaises(ValueError):
                validate_policy(candidate, "2025-26")

    def test_no_hidden_correction_of_model_arithmetic(self):
        profile = TaxProfile(1200000, "2024-25", 35, True)
        response = {
            "old_tax": 10,
            "new_tax": 20,
            "explanation": "Deliberately wrong for a contract test",
            "clauses": ["s87A"],
        }
        result = calculate_with_llm(profile, FakeClient(response))
        self.assertEqual(result["response"]["new_tax"], 20)

    def test_bad_model_money_and_alert_indices_rejected(self):
        with self.assertRaises(ValueError):
            calculate_with_llm(
                TaxProfile(1200000, "2024-25", 35, True),
                FakeClient({"old_tax": True, "new_tax": -1}),
            )
        rows = sample_rows()
        with self.assertRaises(ValueError):
            review_with_llm(
                rows,
                Reference(rows),
                FakeClient(
                    {
                        "alerts": [
                            {"row_index": 999999, "problem": "personal_data", "reason": "invalid"}
                        ]
                    }
                ),
                "test",
            )

    def test_invalid_review_counts_as_measured_failure(self):
        rows = sample_rows()
        alerts, record, error = measured_review(
            rows,
            Reference(rows),
            FakeClient(
                {"alerts": [{"row_index": 999999, "problem": "personal_data", "reason": "invalid"}]}
            ),
            "test",
        )
        self.assertEqual(alerts, [])
        self.assertIsNotNone(error)
        self.assertIn("response", record)
