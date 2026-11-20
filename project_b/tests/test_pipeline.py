import unittest
from project_b.data import PROBLEMS, normalize, structural_controls
from project_b.reference import Reference
from project_b.injector import inject
from project_b.detectors import detect
from project_b.hybrid import run_hybrid


def sample_rows(n=100):
    return [
        normalize(
            {
                "unique_key": str(i),
                "created_date": f"2023-01-01T{(i//60):02d}:{i%60:02d}:00.000",
                "closed_date": "2023-01-03T00:00:00.000",
                "agency": "A" if i % 2 else "B",
                "complaint_type": "Noise" if i % 2 else "Road",
                "descriptor": "Music" if i % 2 else "Pothole",
                "resolution_description": "The case has been closed.",
                "status": "Closed",
                "incident_zip": "10001" if i % 2 else "11201",
                "borough": "MANHATTAN" if i % 2 else "BROOKLYN",
                "latitude": "40.7",
                "longitude": "-73.9",
                "incident_address": f"{i} EXAMPLE STREET",
            }
        )
        for i in range(n)
    ]


class PipelineTests(unittest.TestCase):
    def setUp(self):
        self.rows = sample_rows()
        self.reference = Reference(self.rows)

    def test_all_injections_change_data_and_are_repeatable(self):
        for problem in PROBLEMS:
            with self.subTest(problem=problem):
                first = inject(self.rows, problem, 0.1, 3, self.reference)
                second = inject(self.rows, problem, 0.1, 3, self.reference)
                self.assertEqual(first, second)
                self.assertTrue(first["positive_indices"])
                for i in first["positive_indices"]:
                    if i < len(self.rows):
                        self.assertNotEqual(first["rows"][i], self.rows[i])
                self.assertNotEqual(first["rows"], self.rows)
        self.assertEqual(self.rows, sample_rows())

    def test_hard_rule_recall(self):
        for problem in [
            "schema_change",
            "type_change",
            "date_format",
            "coordinates_swapped",
            "exact_duplicate",
            "negative_duration",
            "zip_borough",
            "complaint_descriptor",
            "resolution_status",
        ]:
            with self.subTest(problem=problem):
                batch = inject(self.rows, problem, 0.1, 3, self.reference)
                flagged = {
                    a["row_index"]
                    for a in detect(batch["rows"], self.reference)
                    if a["problem"] == problem
                }
                self.assertTrue(batch["positive_indices"] <= flagged)

    def test_clean_hard_rules_and_hybrid_budget(self):
        hard = {
            "schema_change",
            "type_change",
            "date_format",
            "coordinates_swapped",
            "exact_duplicate",
            "negative_duration",
        }
        self.assertFalse([a for a in detect(self.rows, self.reference) if a["problem"] in hard])
        result = run_hybrid(self.rows, self.reference, review_budget=2)
        self.assertEqual(result["reviewed_rows"], 0)
        self.assertEqual(result["deferred_rows"], result["candidate_rows"])

    def test_zero_rate_and_invalid_rate(self):
        for problem in PROBLEMS:
            self.assertFalse(
                inject(self.rows, problem, 0, reference=self.reference)["positive_indices"]
            )
        with self.assertRaises(ValueError):
            inject(self.rows, "made_up", 0.1)

    def test_schema_variants_include_drop_and_rename(self):
        renamed = inject(self.rows, "schema_change", 0.1, 3, self.reference)
        dropped = inject(self.rows, "schema_change", 0.1, 4, self.reference)
        self.assertIn("problem", renamed["rows"][0])
        self.assertNotIn("problem", dropped["rows"][0])
        self.assertNotIn("complaint_type", dropped["rows"][0])

    def test_normalization_does_not_change_zip_identifier(self):
        row = normalize({"incident_zip": "00123", "latitude": "40.7"})
        self.assertEqual(row["incident_zip"], "00123")
        self.assertIs(type(row["latitude"]), float)

    def test_controls_do_not_impute(self):
        row = self.rows[0].copy()
        row["descriptor"] = None
        result = structural_controls([row])
        self.assertIsNone(result[0]["descriptor"])

    def test_semantic_candidates_do_not_silently_pass_without_model(self):
        batch = inject(self.rows, "resolution_status", 0.1, 3, self.reference)
        result = run_hybrid(batch["rows"], self.reference)
        flagged = {a["row_index"] for a in result["alerts"] if a["problem"] == "resolution_status"}
        self.assertTrue(batch["positive_indices"] <= flagged)
        self.assertGreater(result["deferred_rows"], 0)
