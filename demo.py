"""A short interview walkthrough; no network requests or changes to reports."""

from project_a.engine import compare
from project_a.models import TaxProfile
from project_a.parser import parse_description
from project_b.data import load_split, structural_controls
from project_b.reference import Reference
from project_b.injector import inject
from project_b.hybrid import run_hybrid


def main():
    profile = TaxProfile(1275010, "2025-26", 35, True)
    comparison = compare(profile)
    print("TAX: FY25 gross INR 1,275,010, resident age 35, no claims")
    print("Old:", comparison["old"]["tax_payable"], "New:", comparison["new"]["tax_payable"])
    print("New-regime ledger:")
    for line in comparison["new"]["tax_ledger"]:
        print(f"  {line['label']}: {line['amount']} [{line['clause']}]")
    print("\nINCOMPLETE DESCRIPTION:")
    for question in parse_description("Meri salary 12 lakh hai")["questions"]:
        print(" ", question)
    _, train, holdout = load_split()
    reference = Reference(train)
    controls = structural_controls(holdout)[:100]
    batch = inject(controls, "negative_duration", 0.1, 7, reference)
    result = run_hybrid(batch["rows"], reference)
    detected = {a["row_index"] for a in result["alerts"] if a["problem"] == "negative_duration"}
    print(
        "\nQUALITY: negative durations detected",
        len(detected & batch["positive_indices"]),
        "/",
        len(batch["positive_indices"]),
    )
    for alert in result["alerts"]:
        if alert["problem"] == "negative_duration":
            print(" ", alert["unique_key"], alert["reason"])
            break


if __name__ == "__main__":
    main()
