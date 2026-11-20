"""Prepare independent NET-income checks for the official calculator asset.

No production calculator is imported. Deductions are intentionally absent: this
calculator accepts net taxable income, so it cannot independently verify HRA/80D.
"""

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from common.io import ROOT, write_json
from project_a.tests.oracle import expected_tax

SALARIES = [
    0,
    250000,
    300000,
    500000,
    550000,
    551000,
    700000,
    750000,
    775000,
    776000,
    800000,
    1000000,
    1075000,
    1200000,
    1275000,
    1500000,
    1575000,
    2000000,
    2400000,
    2475000,
    5000000,
    5050000,
    5075000,
    5100000,
    10050000,
    10075000,
    20050000,
    20075000,
    50050000,
    50075000,
]


if __name__ == "__main__":
    queued, calls = [], []
    for index, salary in enumerate(SALARIES):
        profile = {"salary": salary, "financial_year": "2024-25", "age": 35, "resident": True}
        expected = {regime: expected_tax(salary, "2024-25", regime) for regime in ["old", "new"]}
        case_id = f"official-net-{index+1:02d}"
        queued.append(
            {
                "case_id": case_id,
                "input": profile,
                "engine_expected": expected,
                "official_old": None,
                "official_new": None,
                "status": "pending",
                "evidence": None,
                "scope": "Slab/rebate/surcharge/cess validation on independently specified net salary; deductions and language parsing not externally checked",
            }
        )
        for regime in ["old", "new"]:
            calls.append(
                {
                    "case_id": case_id,
                    "regime": regime,
                    "assessment_year": "2025-26",
                    "age": 35,
                    "resident": True,
                    "net_taxable_income": max(0, salary - (50000 if regime == "old" else 75000)),
                }
            )
    write_json(ROOT / "data/official_calculator/check_inputs.json", calls)
    write_json(ROOT / "project_a/tests/fixtures/official_checks.json", queued)
