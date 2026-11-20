"""Deterministic salary tax calculation with a reconciling statutory ledger.

One fixed interpreter executes either hand-authored or LLM-compiled policy data.
Never execute Python emitted by a model.
"""

from decimal import Decimal, ROUND_HALF_UP
import hashlib
import json
from .models import TaxProfile
from .policy import hand_policy

D = Decimal
CLAUSES = {
    "standard": "Income-tax Act 1961 s16(ia); Finance (No.2) Act 2024 s10",
    "hra": "Income-tax Act 1961 s10(13A), Income-tax Rules 1962 r2A",
    "80c": "Income-tax Act 1961 ss80C,80CCE",
    "nps": "Income-tax Act 1961 s80CCD(1B); amount not also claimed in 80C",
    "health": "Income-tax Act 1961 s80D(2),(2A),(2B),(2C),(4)",
    "home": "Income-tax Act 1961 s24(b), s71(3A); self-occupied property",
    "old_slabs": "Finance (No.2) Act 2024 First Schedule Part III Paragraph A; unchanged Finance Act 2025",
    "new_slabs": "Income-tax Act 1961 s115BAC(1A), as amended by Finance (No.2) Act 2024 / Finance Act 2025 s24",
    "rebate": "Income-tax Act 1961 s87A, proviso; Finance Act 2025 s20 for FY2025-26",
    "surcharge": "Applicable Finance Act First Schedule Paragraph A surcharge and marginal-relief provisos",
    "cess": "Applicable Finance Act s2: Health and Education Cess, 4% after rebate/surcharge relief",
    "income_rounding": "Income-tax Act 1961 s288A",
    "tax_rounding": "Income-tax Act 1961 s288B",
}


def round_ten(value):
    return (D(value) / 10).quantize(D(1), rounding=ROUND_HALF_UP) * 10


def _slabs(income, slabs):
    lower, tax, lines = D(0), D(0), []
    for upper, rate in slabs:
        amount = max(D(0), min(D(income), D(upper) if upper is not None else D(income)) - lower)
        charge = amount * D(rate)
        lines.append(
            {
                "lower": str(lower),
                "upper": upper,
                "rate": rate,
                "taxable_in_band": str(amount),
                "amount": str(charge),
            }
        )
        tax += charge
        if upper is None:
            break
        lower = D(upper)
    return tax, lines


def calculate(profile: TaxProfile, regime="new", policy=None):
    if regime not in ["old", "new"]:
        raise ValueError("Regime must be old or new")
    p = policy or hand_policy(profile.financial_year)
    if p["financial_year"] != profile.financial_year:
        raise ValueError("Policy year does not match input year")
    policy_hash = hashlib.sha256(json.dumps(p, sort_keys=True).encode()).hexdigest()
    deductions = []

    def deduction(label, amount, clause):
        deductions.append({"label": label, "amount": str(amount), "clause": CLAUSES[clause]})
        return D(amount)

    standard = deduction(
        "Standard deduction", min(profile.salary, p[f"standard_{regime}"]), "standard"
    )
    other = D(0)
    if regime == "old":
        for index, period in enumerate(profile.hra_periods):
            exemption = max(
                D(0),
                min(
                    D(period.received),
                    D(period.salary_basis) * (D(".5") if period.metro else D(".4")),
                    D(period.rent) - D(period.salary_basis) * D(".1"),
                ),
            )
            other += deduction(f"HRA exemption, period {index+1}", exemption, "hra")
        interest = min(
            profile.home_interest,
            p["home_qualifying"] if profile.home_loan_qualifies_2l else p["home_other"],
        )
        other += deduction(
            "Self-occupied housing interest / allowed house-property loss set-off", interest, "home"
        )
        family_cap = (
            p["health_senior"]
            if profile.family_senior or (profile.resident and profile.age >= 60)
            else p["health_regular"]
        )
        parent_cap = p["health_senior"] if profile.parents_senior else p["health_regular"]
        # The 5,000 check-up limit is combined across both groups.
        self_checkup = min(
            profile.checkup_self,
            p["checkup_cap"],
            max(0, family_cap - profile.health_self - profile.medical_self),
        )
        parent_checkup = min(
            profile.checkup_parents,
            p["checkup_cap"] - self_checkup,
            max(0, parent_cap - profile.health_parents - profile.medical_parents),
        )
        health = min(family_cap, profile.health_self + profile.medical_self + self_checkup) + min(
            parent_cap, profile.health_parents + profile.medical_parents + parent_checkup
        )
        available = max(D(0), D(profile.salary) - standard - other)
        chapter = [
            (
                "80C (eligible investments, including any employee EPF)",
                min(profile.section_80c, p["cap_80c"]),
                "80c",
            ),
            (
                "Additional own NPS (no double claim)",
                min(profile.nps_80ccd_1b, p["cap_nps"]),
                "nps",
            ),
            ("80D eligible health expenditure", health, "health"),
        ]
        for label, amount, clause in chapter:
            allowed = min(available, D(amount))
            other += deduction(label, allowed, clause)
            available -= allowed
    taxable_before_rounding = max(D(0), D(profile.salary) - standard - other)
    taxable = round_ten(taxable_before_rounding)
    slabs = [list(band) for band in p[f"{regime}_slabs"]]
    if regime == "old" and profile.resident:
        slabs[0][0] = 500000 if profile.age >= 80 else 300000 if profile.age >= 60 else 250000
    base_tax, slab_lines = _slabs(taxable, slabs)
    ledger = []

    def entry(label, amount, clause, **detail):
        ledger.append({"label": label, "amount": str(amount), "clause": CLAUSES[clause], **detail})

    for line in slab_lines:
        entry("Slab tax", line.pop("amount"), f"{regime}_slabs", **line)
    threshold, cap = p[f"rebate_{regime}_threshold"], p[f"rebate_{regime}_cap"]
    rebate = D(0)
    if profile.resident:
        if taxable <= threshold:
            rebate = min(base_tax, D(cap))
        elif regime == "new":
            rebate = max(D(0), base_tax - (taxable - threshold))
    entry("87A rebate including marginal relief", -rebate, "rebate")
    tax = base_tax - rebate
    bands, rate = p[f"surcharge_{regime}"], D(0)
    for boundary, candidate in bands:
        if taxable > boundary:
            rate = D(candidate)
    surcharge = tax * rate
    entry("Surcharge", surcharge, "surcharge", rate=str(rate))
    before_relief = tax + surcharge
    after_relief, previous_rate = before_relief, D(0)
    for boundary, candidate in bands:
        if taxable > boundary and D(candidate) > previous_rate:
            threshold_tax, _ = _slabs(D(boundary), slabs)
            ceiling = threshold_tax * (1 + previous_rate) + taxable - boundary
            after_relief = min(after_relief, ceiling)
        previous_rate = D(candidate)
    relief = before_relief - after_relief
    entry("Surcharge marginal relief", -relief, "surcharge")
    cess = after_relief * D(p["cess"])
    entry("Health and education cess", cess, "cess", rate=p["cess"])
    unrounded = after_relief + cess
    payable = round_ten(unrounded)
    entry("Final payable rounding", payable - unrounded, "tax_rounding")
    assert sum(D(row["amount"]) for row in ledger) == payable
    return {
        "financial_year": profile.financial_year,
        "policy_sha256": policy_hash,
        "regime": regime,
        "gross_salary": profile.salary,
        "deductions": deductions,
        "taxable_before_rounding": str(taxable_before_rounding),
        "taxable_income": int(taxable),
        "income_rounding_clause": CLAUSES["income_rounding"],
        "tax_ledger": ledger,
        "tax_before_final_rounding": str(unrounded),
        "tax_payable": int(payable),
    }


def compare(profile, policy=None):
    old, new = calculate(profile, "old", policy), calculate(profile, "new", policy)
    difference = old["tax_payable"] - new["tax_payable"]
    return {
        "old": old,
        "new": new,
        "recommendation": "new" if difference > 0 else "old" if difference < 0 else "either",
        "saving": abs(difference),
        "scope": "Annual salary only; no TDS, interest, penalties or other income heads. Inputs must already satisfy deduction eligibility.",
    }
