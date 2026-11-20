"""Conservative first pass. A clarification is cheaper than an invented tax input.

Supported phrases deliberately stay small. Unrecognised deduction details are
escalated to questions; the optional Gemini extractor uses the same validation gate.
"""

import re
from decimal import Decimal
from .models import TaxProfile

AMOUNT = r"(?:rs\.?\s*|inr\s*|₹\s*)?(\d[\d,]*(?:\.\d+)?)\s*(crores?|cr\b|lakhs?|lacs?|lpa\b|lakh\b|l\b|k\b|thousand)?"


def money(number, unit):
    multipliers = {"k": 1000, "thousand": 1000, "cr": 10000000}
    unit = (unit or "").lower()
    multiplier = multipliers.get(
        unit,
        (
            10000000
            if unit.startswith("crore")
            else 100000 if unit.startswith(("lakh", "lac")) or unit in ["lpa", "l"] else 1
        ),
    )
    value = Decimal(number.replace(",", "")) * multiplier
    if value != value.to_integral_value():
        raise ValueError("Please supply whole-rupee annual amounts")
    return int(value)


def parse_description(text):
    if not isinstance(text, str) or not text.strip() or len(text) > 12000:
        return {
            "status": "needs_clarification",
            "fields": {},
            "questions": ["Please describe your annual salary and financial year."],
            "evidence": [],
        }
    t = text.lower()
    values, questions, evidence = {}, [], []

    def set_field(name, value, quote):
        if name in values and values[name] != value:
            questions.append(f"Conflicting {name}: {values[name]} and {value}. Which is correct?")
        else:
            values[name] = value
        evidence.append({"field": name, "value": value, "text": quote})

    other_income = list(
        re.finditer(
            r"\b(capital gains?|business income|freelanc\w*|rental income|interest income|dividends?)\b",
            t,
        )
    )
    positive_other_income = [
        m
        for m in other_income
        if not re.search(r"\b(?:no|without|zero)\s*$", t[max(0, m.start() - 15) : m.start()])
    ]
    if positive_other_income:
        return {
            "status": "out_of_scope",
            "fields": {},
            "questions": [
                "This service supports salary income only, with self-occupied housing interest. Separate any other income first."
            ],
            "evidence": [],
        }
    for match in re.finditer(r"\b(?:(fy|ay)\s*)?(202[4-6]\s*[-/]\s*2[5-7])\b", t):
        year = re.sub(r"\s", "", match[2]).replace("/", "-")
        if match[1] == "ay":
            year = {"2025-26": "2024-25", "2026-27": "2025-26"}.get(year, "unsupported")
        set_field("financial_year", year, match[0])
    for match in re.finditer(
        r"\b(?:age\s*(?:is\s*)?(\d{2,3})|(\d{2,3})\s*(?:years? old|saal))\b", t
    ):
        set_field("age", int(match[1] or match[2]), match[0])
    nonresident = bool(
        re.search(r"\b(nri|non[- ]resident|not (?:an? )?(?:indian |tax )?resident)\b", t)
    )
    resident = bool(
        re.search(
            r"\b(indian resident|resident in india|tax resident of india|resident hu|resident hoon)\b",
            t,
        )
    )
    if nonresident:
        set_field("resident", False, "nonresident statement")
    if resident:
        set_field("resident", True, "resident statement")
    gross_pattern = (
        r"(?<!basic )(?<!net )\b(?:gross(?: annual)? salary|annual(?: gross)? salary|meri salary|salary)\s*(?:is|hai|of|=|:)?\s*"
        + AMOUNT
    )
    for match in re.finditer(gross_pattern, t):
        amount = money(match[1], match[2])
        tail = t[match.end() : match.end() + 25]
        if re.match(r"\s*(?:per month|monthly|/month|/mo\b|mahina)", tail):
            amount *= 12
        elif not (
            match[2] == "lpa"
            or re.match(r"\s*(?:per year|annually|annual|/year|pa\b)", tail)
            or re.search(r"\bannual\b", match[0])
        ):
            questions.append("Is the stated salary annual gross salary or monthly gross salary?")
        set_field("salary", amount, match[0] + tail[:15])
    if re.search(r"\b(ctc|in[- ]hand|take[- ]home|net salary)\b", t):
        questions.append(
            "What is your annual taxable gross salary before exemptions and standard deduction? CTC and take-home are not the same amount."
        )
    for field, pattern in [
        ("section_80c", r"\b80c\s*(?:is|=|:|of)?\s*"),
        ("nps_80ccd_1b", r"\b(?:additional nps|80ccd\(1b\))\s*(?:is|=|:|of)?\s*"),
    ]:
        for match in re.finditer(pattern + AMOUNT, t):
            set_field(field, money(match[1], match[2]), match[0])
    if re.search(r"\b80c\b", t) and "section_80c" not in values:
        questions.append("What is the total eligible 80C amount, including employee EPF?")
    if re.search(r"\bnps\b", t) and "nps_80ccd_1b" not in values:
        questions.append(
            "How much own NPS is claimed only under 80CCD(1B), excluding anything already counted under 80C?"
        )
    if re.search(r"\b(hra|rent|basic|metro|house rent)\b", t):
        questions.append(
            "For each HRA period provide HRA received, rent paid, salary basis (basic + eligible DA + turnover commission), and city; all amounts for the same period."
        )
    if re.search(r"\b(80d|mediclaim|health insurance|medical|parents? premium)\b", t):
        questions.append(
            "Split 80D payments between family and parents: noncash premiums, check-ups, uninsured senior medical expenses, and resident senior eligibility."
        )
    if re.search(r"\b(home loan|home interest|housing loan|self[- ]occupied)\b", t):
        questions.append(
            "What is the annual interest on your self-occupied home, and does the loan meet the 2 lakh acquisition/construction conditions (otherwise 30,000)?"
        )
    complete = bool(
        re.search(
            r"\b(no deductions|no other deductions|only these deductions|baaki koi deduction nahi|koi deduction nahi)\b",
            t,
        )
    )
    if re.search(r"\bno deductions\b", t) and any(
        values.get(f, 0) for f in ["section_80c", "nps_80ccd_1b"]
    ):
        questions.append(
            "You stated both a deduction and no deductions. Which deductions should be included?"
        )
    if not complete:
        questions.append(
            "Are there any HRA, 80C/EPF, additional own NPS, 80D or self-occupied housing-interest claims? Confirm amounts or explicitly confirm none."
        )
    for field, prompt in [
        ("financial_year", "Which financial year: 2024-25 or 2025-26?"),
        ("salary", "What is your annual gross salary in INR?"),
        ("age", "What is your age at the end of that financial year?"),
        ("resident", "Are you a resident in India for income-tax purposes for that year?"),
    ]:
        if field not in values:
            questions.append(prompt)
    questions = list(dict.fromkeys(questions))
    if not questions:
        try:
            TaxProfile.from_dict(values)
        except (TypeError, ValueError) as exc:
            questions.append(str(exc))
    return {
        "status": "needs_clarification" if questions else "ready",
        "fields": values,
        "questions": questions,
        "evidence": evidence,
    }
