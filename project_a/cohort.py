"""A fixed, input-stratified 200-profile model comparison, independent of answers."""
from common.io import ROOT, read_json


def comparison_cases(cases, limit=None):
    identifiers = read_json(ROOT / "project_a/tests/fixtures/comparison_cohort.json")["case_ids"]
    indexed = {case["id"]: case for case in cases}
    selected = [indexed[identifier] for identifier in identifiers]
    if limit is not None:
        selected = selected[::max(1, len(selected)//limit)][:limit]
    return selected


def repeat_case(cases):
    return next(case for case in cases if case["input"]["financial_year"] == "2025-26"
                and case["input"]["salary"] == 1275010
                and set(case["input"]) == {"salary", "financial_year", "age", "resident"})
