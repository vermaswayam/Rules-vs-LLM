"""Author explicit expected cases before production implementation; never called by reproduce."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from common.io import ROOT, write_json
from project_a.tests.oracle import expected_tax


def main():
    cases = []
    thresholds = [
        0,
        250000,
        300000,
        400000,
        500000,
        700000,
        722220,
        722230,
        800000,
        1000000,
        1200000,
        1270580,
        1270590,
        1500000,
        1600000,
        2000000,
        2400000,
        5000000,
        10000000,
        20000000,
        50000000,
    ]
    for year in ["2024-25", "2025-26"]:
        salaries = sorted(
            {
                max(0, threshold + standard + delta)
                for threshold in thresholds
                for standard in [50000, 75000]
                for delta in [-11, -5, -1, 0, 1, 4, 5, 10, 11]
            }
        )
        for salary in salaries:
            profile = {"salary": salary, "financial_year": year, "age": 35, "resident": True}
            cases.append(
                {
                    "id": f"{year}-salary-{salary}",
                    "input": profile,
                    "expected": {
                        regime: expected_tax(salary, year, regime) for regime in ["old", "new"]
                    },
                    "basis": "Independent closed-form statutory oracle; not official calculator validation",
                }
            )
        for age, resident in [
            (59, True),
            (60, True),
            (79, True),
            (80, True),
            (80, False),
            (35, False),
        ]:
            for salary in [300000, 550000, 550005, 775005, 1275005, 5050005, 10050005, 50050005]:
                cases.append(
                    {
                        "id": f"{year}-age{age}-resident{resident}-{salary}",
                        "input": {
                            "salary": salary,
                            "financial_year": year,
                            "age": age,
                            "resident": resident,
                        },
                        "expected": {
                            r: expected_tax(salary, year, r, age, resident) for r in ["old", "new"]
                        },
                        "basis": "Independent statutory oracle",
                    }
                )
        # These deductions are worked out explicitly, independently of the engine.
        examples = [
            ("80c-cap", {"section_80c": 200000}, 150000),
            ("nps-cap", {"nps_80ccd_1b": 70000}, 50000),
            (
                "80d-parents-senior",
                {"health_self": 30000, "health_parents": 60000, "parents_senior": True},
                75000,
            ),
            ("80d-under60", {"health_self": 30000, "health_parents": 30000}, 50000),
            ("80d-checkup-global-cap", {"checkup_self": 4000, "checkup_parents": 4000}, 5000),
            ("80d-uninsured-senior", {"medical_parents": 60000, "parents_senior": True}, 50000),
            ("loan-qualifying", {"home_interest": 300000, "home_loan_qualifies_2l": True}, 200000),
            ("loan-repairs", {"home_interest": 90000, "home_loan_qualifies_2l": False}, 30000),
            (
                "hra-metro",
                {
                    "hra_periods": [
                        {"salary_basis": 600000, "received": 240000, "rent": 300000, "metro": True}
                    ]
                },
                240000,
            ),
            (
                "hra-nonmetro",
                {
                    "hra_periods": [
                        {"salary_basis": 600000, "received": 300000, "rent": 400000, "metro": False}
                    ]
                },
                240000,
            ),
            (
                "hra-no-rent",
                {
                    "hra_periods": [
                        {"salary_basis": 600000, "received": 240000, "rent": 0, "metro": True}
                    ]
                },
                0,
            ),
            (
                "hra-two-periods",
                {
                    "hra_periods": [
                        {"salary_basis": 300000, "received": 120000, "rent": 90000, "metro": True},
                        {
                            "salary_basis": 300000,
                            "received": 120000,
                            "rent": 180000,
                            "metro": False,
                        },
                    ]
                },
                180000,
            ),
        ]
        for label, fields, deduction in examples:
            for salary in [1200000, 2000000]:
                cases.append(
                    {
                        "id": f"{year}-{label}-{salary}",
                        "input": {
                            "salary": salary,
                            "financial_year": year,
                            "age": 35,
                            "resident": True,
                            **fields,
                        },
                        "expected": {
                            r: expected_tax(salary, year, r, old_deductions=deduction)
                            for r in ["old", "new"]
                        },
                        "basis": f"Manual eligible old deduction {deduction}; independent slab oracle",
                    }
                )
        for name, cap, extra in [
            ("section_80c", 150000, {}),
            ("nps_80ccd_1b", 50000, {}),
            ("health_self", 25000, {}),
            ("health_parents", 25000, {}),
            ("health_parents", 50000, {"parents_senior": True}),
            ("checkup_self", 5000, {}),
            ("home_interest", 200000, {"home_loan_qualifies_2l": True}),
            ("home_interest", 30000, {"home_loan_qualifies_2l": False}),
        ]:
            for delta in [-1, 0, 1]:
                amount = cap + delta
                salary = 2000000
                deduction = min(amount, cap)
                cases.append(
                    {
                        "id": f"{year}-deduction-boundary-{name}-{cap}-{delta}",
                        "input": {
                            "salary": salary,
                            "financial_year": year,
                            "age": 35,
                            "resident": True,
                            name: amount,
                            **extra,
                        },
                        "expected": {
                            r: expected_tax(salary, year, r, old_deductions=deduction)
                            for r in ["old", "new"]
                        },
                        "basis": f"Explicit cap min({amount},{cap}); independent closed-form tax oracle",
                    }
                )
    write_json(ROOT / "project_a/tests/fixtures/tax_cases.json", cases)
    print(f"Wrote {len(cases)} expected cases; independent official observations left unchanged")


if __name__ == "__main__":
    main()
