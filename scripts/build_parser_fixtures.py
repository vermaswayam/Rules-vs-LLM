"""50 deliberately varied descriptions with hand-labelled response expectations."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from common.io import ROOT, write_json

EXAMPLES = [
    (
        "Annual salary 12 lakh. FY 2024-25. Age 30. Indian resident. No deductions.",
        "ready",
        {"salary": 1200000},
    ),
    (
        "FY 2025-26, meri salary 8 lpa hai, age 28, resident hu, baaki koi deduction nahi.",
        "ready",
        {"salary": 800000},
    ),
    (
        "Salary Rs 100000 per month. FY 2024-25. Age 40. Resident in India. No deductions.",
        "ready",
        {"salary": 1200000},
    ),
    (
        "Annual gross salary INR 1,275,000; FY 2025-26; age 35; Indian resident; no deductions.",
        "ready",
        {"salary": 1275000},
    ),
    (
        "Annual salary 20 lakh, age 60, Indian resident, FY 2024-25, 80C 1.5 lakh. Only these deductions.",
        "ready",
        {"section_80c": 150000},
    ),
    ("FY 2025-26. Salary 18 lpa. Age 45. NRI. No deductions.", "ready", {"resident": False}),
    (
        "Annual salary 2 crore, FY 2024-25, age 55, Indian resident, no deductions.",
        "ready",
        {"salary": 20000000},
    ),
    (
        "Annual salary 6 crore; age 62; resident in India; FY 2025-26; no deductions.",
        "ready",
        {"salary": 60000000},
    ),
    (
        "Annual salary 9 lakh; age 80; Indian resident; FY 2024-25; no deductions.",
        "ready",
        {"age": 80},
    ),
    (
        "Annual salary 0. FY 2024-25. Age 30. Indian resident. No deductions.",
        "ready",
        {"salary": 0},
    ),
    (
        "Annual salary 12 lakh; FY 2025-26; age 35; Indian resident; additional NPS 50k; only these deductions.",
        "ready",
        {"nps_80ccd_1b": 50000},
    ),
    (
        "Annual salary 20 lakh, FY 2024-25, age 35, Indian resident, 80C 2 lakh, no other deductions.",
        "ready",
        {"section_80c": 200000},
    ),
    (
        "Annual salary 7.75 lakh FY 2024-25 age 25 Indian resident no deductions.",
        "ready",
        {"salary": 775000},
    ),
    (
        "Annual salary 12.75 lakh FY 2025-26 age 25 Indian resident no deductions.",
        "ready",
        {"salary": 1275000},
    ),
    (
        "Annual salary 15 lakh AY 2025-26 age 35 Indian resident no deductions.",
        "ready",
        {"financial_year": "2024-25"},
    ),
    (
        "Meri salary 10 lpa, FY 2024-25, 30 saal, resident hoon, koi deduction nahi.",
        "ready",
        {"salary": 1000000},
    ),
    (
        "Annual salary 900000 FY 2025/26 age is 39 Indian resident no deductions.",
        "ready",
        {"financial_year": "2025-26"},
    ),
    (
        "Salary 75k monthly FY 2024-25 age 32 Indian resident no deductions.",
        "ready",
        {"salary": 900000},
    ),
    (
        "Annual salary 550000 FY 2024-25 age 80 non-resident no deductions.",
        "ready",
        {"resident": False},
    ),
    (
        "Annual salary 1275010 FY 2025-26 age 35 Indian resident no deductions.",
        "ready",
        {"salary": 1275010},
    ),
    ("I earn well. What tax?", "needs_clarification", {}),
    ("Salary 12 lakh FY 2024-25 age 30 Indian resident no deductions.", "needs_clarification", {}),
    ("Annual salary 12 lakh, age 30, Indian resident, no deductions.", "needs_clarification", {}),
    ("Annual salary 12 lakh FY 2024-25 Indian resident no deductions.", "needs_clarification", {}),
    ("Annual salary 12 lakh FY 2024-25 age 30 no deductions.", "needs_clarification", {}),
    ("Annual salary 12 lakh FY 2024-25 age 30 Indian resident.", "needs_clarification", {}),
    ("CTC 20 lakh FY 2024-25 age 30 Indian resident no deductions.", "needs_clarification", {}),
    (
        "Net salary 100000 monthly FY 2025-26 age 32 Indian resident no deductions.",
        "needs_clarification",
        {},
    ),
    (
        "Annual salary 12 lakh and annual salary 15 lakh. FY 2024-25 age 30 Indian resident no deductions.",
        "needs_clarification",
        {},
    ),
    (
        "Annual salary 12 lakh FY 2024-25 FY 2025-26 age 30 Indian resident no deductions.",
        "needs_clarification",
        {},
    ),
    (
        "Annual salary 12 lakh FY 2024-25 age 30 age 40 Indian resident no deductions.",
        "needs_clarification",
        {},
    ),
    (
        "Annual salary 12 lakh FY 2024-25 age 30 Indian resident NRI no deductions.",
        "needs_clarification",
        {},
    ),
    (
        "Annual salary 12 lakh FY 2024-25 age 30 Indian resident 80C 1 lakh no deductions.",
        "needs_clarification",
        {},
    ),
    (
        "Annual salary 12 lakh FY 2024-25 age 30 Indian resident HRA 2 lakh no other deductions.",
        "needs_clarification",
        {},
    ),
    (
        "Annual salary 12 lakh FY 2024-25 age 30 Indian resident rent 20k monthly no other deductions.",
        "needs_clarification",
        {},
    ),
    (
        "Annual salary 12 lakh FY 2024-25 age 30 Indian resident health insurance 30k no other deductions.",
        "needs_clarification",
        {},
    ),
    (
        "Annual salary 12 lakh FY 2024-25 age 30 Indian resident parents premium 60k no other deductions.",
        "needs_clarification",
        {},
    ),
    (
        "Annual salary 12 lakh FY 2024-25 age 30 Indian resident home loan 2 lakh no other deductions.",
        "needs_clarification",
        {},
    ),
    (
        "Annual salary 12 lakh FY 2024-25 age 30 Indian resident NPS 50k no other deductions.",
        "needs_clarification",
        {},
    ),
    (
        "Annual salary 12 lakh FY 2026-27 age 30 Indian resident no deductions.",
        "needs_clarification",
        {},
    ),
    ("Bhai tax bata do salary achchi hai.", "needs_clarification", {}),
    (
        "Annual salary 12 lakh FY 2024-25 age 17 Indian resident no deductions.",
        "needs_clarification",
        {},
    ),
    (
        "Annual salary 12 lakh FY 2024-25 age 30 Indian resident 80C 1 lakh 80C 2 lakh only these deductions.",
        "needs_clarification",
        {},
    ),
    (
        "Annual salary 12 lakh FY 2024-25 age 30 Indian resident CTC 18 lakh no deductions.",
        "needs_clarification",
        {},
    ),
    (
        "Annual salary 12 lakh FY 2024-25 age 30 Indian resident 80D 25000 only these deductions.",
        "needs_clarification",
        {},
    ),
    (
        "Annual salary 12 lakh FY 2024-25 age 30 Indian resident capital gains 50000 no deductions.",
        "out_of_scope",
        {},
    ),
    (
        "Annual salary 12 lakh FY 2024-25 age 30 Indian resident business income 2 lakh no deductions.",
        "out_of_scope",
        {},
    ),
    ("Freelancing income 10 lakh, how much tax?", "out_of_scope", {}),
    (
        "Annual salary 12 lakh and rental income 2 lakh FY 2024-25 age 30 Indian resident.",
        "out_of_scope",
        {},
    ),
    (
        "Annual salary 12 lakh plus dividend 20000 FY 2025-26 age 30 Indian resident.",
        "out_of_scope",
        {},
    ),
]

if __name__ == "__main__":
    write_json(
        ROOT / "project_a/tests/fixtures/descriptions.json",
        [
            {
                "id": f"language-{i:02d}",
                "text": t,
                "expected_status": status,
                "expected_fields": fields,
            }
            for i, (t, status, fields) in enumerate(EXAMPLES, 1)
        ],
    )
