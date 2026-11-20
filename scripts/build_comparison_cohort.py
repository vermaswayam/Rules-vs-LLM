"""Freeze the input strata before the bulk model experiment; no outputs are read."""
import random
import re
from common.io import ROOT, read_json, write_json


def main():
    cases = read_json(ROOT / "project_a/tests/fixtures/tax_cases.json")
    chosen = []
    strata = {}
    for year in ["2024-25", "2025-26"]:
        rng = random.Random(20261119 + int(year[:4]))
        group = [c for c in cases if c["input"]["financial_year"] == year]
        salary = [c for c in group if "-salary-" in c["id"]]
        ages = [c for c in group if "-age" in c["id"]]
        deductions = [c for c in group if c not in salary and c not in ages]
        assert len(deductions) == 48
        age_groups = {}
        for case in ages:
            tag = re.search(r"age\d+-resident(?:True|False)", case["id"])[0]
            age_groups.setdefault(tag, []).append(case)
        selected_ages = [c for tag in sorted(age_groups) for c in rng.sample(age_groups[tag], 2)]
        selected_salary = []
        def add_salary(target):
            candidate = min(salary, key=lambda c: (abs(c["input"]["salary"]-target), c["id"]))
            if candidate not in selected_salary:
                selected_salary.append(candidate)
        for taxable in [250000, 500000, 1000000, 5000000, 10000000, 20000000, 50000000]:
            for delta in [0, 5]:
                add_salary(taxable+50000+delta)
        new_boundaries = [300000, 700000, 1000000, 1200000, 1500000] if year == '2024-25' else [400000, 800000, 1200000, 1600000, 2000000, 2400000]
        for taxable in new_boundaries:
            for delta in [0, 5]:
                add_salary(taxable+75000+delta)
        if year == '2025-26':
            add_salary(1275010)
        remaining = [c for c in salary if c not in selected_salary]
        selected_salary += rng.sample(remaining, 40-len(selected_salary))
        selected = deductions + selected_ages + selected_salary
        assert len(selected) == 100
        chosen += selected
        strata[year] = {"deduction_cases": len(deductions), "age_residency_cases": len(selected_ages), "salary_boundaries": len(selected_salary)}
    assert len({c['id'] for c in chosen}) == 200
    write_json(ROOT / 'project_a/tests/fixtures/comparison_cohort.json', {
        'selection': 'Input-only stratification: 100 profiles per FY; all 48 deduction cases, two per age/residency group, 40 salary-boundary cases. Fixed seed; no model answers or expected tax used in selection.',
        'seed': 20261119, 'strata': strata, 'case_ids': [c['id'] for c in chosen],
        'note': 'The one initial connectivity probe is retained in the FY25 boundary stratum. Both deterministic engines are checked on all 916 profiles and on this matched cohort.'})
    print('Frozen 200-case model cohort', strata)


if __name__ == '__main__':
    main()
