"""An LLM emits a declarative policy, then a fixed interpreter executes it.

Automated acceptance is not described as a human legal review. The bundled
Codex-authored candidates are independently checked against frozen fixtures.
"""

import argparse
from decimal import Decimal, InvalidOperation
import json
from functools import lru_cache
from common.io import ROOT, read_json, write_json, digest
from common.gemini import Gemini, ModelOutputError
from .engine import calculate, compare
from .llm_query import rule_text
from .models import TaxProfile
from .policy import hand_policy


def validate_policy(policy, year):
    expected = hand_policy(year)
    if not isinstance(policy, dict) or set(policy) != set(expected):
        raise ValueError("Compiled policy has missing or unknown fields")
    if policy["financial_year"] != year:
        raise ValueError("Compiled year mismatch")

    def valid_rate(value):
        try:
            rate = Decimal(value)
            return type(value) is str and rate.is_finite() and 0 <= rate <= 1
        except (InvalidOperation, TypeError, ValueError):
            return False

    for key, value in expected.items():
        candidate = policy[key]
        if type(candidate) is not type(value):
            raise ValueError(f"Invalid policy field type: {key}")
        if isinstance(value, int) and candidate < 0:
            raise ValueError(f"Negative limit: {key}")
        if key == "cess" and not valid_rate(candidate):
            raise ValueError("Invalid cess rate")
        if key.endswith("_slabs"):
            previous = -1
            for index, pair in enumerate(candidate):
                if not isinstance(pair, list) or len(pair) != 2:
                    raise ValueError("Invalid slab shape")
                upper, rate = pair
                if upper is None:
                    if index != len(candidate) - 1:
                        raise ValueError("Open slab must be last")
                elif type(upper) is not int or upper <= previous:
                    raise ValueError("Slabs must increase")
                else:
                    previous = upper
                if not valid_rate(rate):
                    raise ValueError("Invalid slab rate")
            if not candidate or candidate[-1][0] is not None:
                raise ValueError("Missing top slab")
        if key.startswith("surcharge_"):
            previous = -1
            for pair in candidate:
                if not isinstance(pair, list) or len(pair) != 2:
                    raise ValueError("Invalid surcharge shape")
                threshold, rate = pair
                if type(threshold) is not int or threshold <= previous or not valid_rate(rate):
                    raise ValueError("Invalid surcharge threshold/rate")
                previous = threshold
    return policy


@lru_cache(maxsize=2)
def load_policy(year):
    path = ROOT / f"project_a/policies/compiled_{year}.json"
    return validate_policy(read_json(path), year)


def compiled_compare(profile):
    return compare(profile, load_policy(profile.financial_year))


def acceptance(policy, year):
    validate_policy(policy, year)
    failures = []
    cases = read_json(ROOT / "project_a/tests/fixtures/tax_cases.json")
    for case in cases:
        if case["input"]["financial_year"] != year:
            continue
        for regime in ["old", "new"]:
            actual = calculate(TaxProfile.from_dict(case["input"]), regime, policy)["tax_payable"]
            if actual != case["expected"][regime]:
                failures.append(
                    {
                        "case": case["id"],
                        "regime": regime,
                        "actual": actual,
                        "expected": case["expected"][regime],
                    }
                )
    return failures


def compile_with_gemini(year, client):
    template = hand_policy(year)
    # Only schema/types are provided, not the answer's numerical values.
    schema_fields = {}
    for key, value in template.items():
        if key.endswith("_slabs") or key.startswith("surcharge_"):
            schema_fields[key] = (
                "list of [upper INR or null, decimal rate string]"
                if key.endswith("_slabs")
                else "list of [strict threshold INR, decimal rate string]"
            )
        else:
            schema_fields[key] = type(value).__name__
    prompt = (
        "Compile the following legal rules into a JSON policy. Return an object with only field policy_json, whose value is the serialized JSON policy. No code, imports or expressions. All rates are decimal strings, amounts integers. Required fields/types: "
        + json.dumps(schema_fields)
        + "\nRULES:\n"
        + rule_text(year)
    )
    if year == '2025-26':
        prompt = ('TARGET FINANCIAL YEAR: 2025-26 (AY 2026-27). Emit financial_year="2025-26". '
                  'The FY2024 bundle is the baseline only. Apply every FY2025 amendment at the end, '
                  'including the replacement new slabs, 1,200,000 rebate threshold and 60,000 cap.\n' + prompt)
    record = client.generate(
        prompt,
        {
            "type": "OBJECT",
            "properties": {"policy_json": {"type": "STRING"}},
            "required": ["policy_json"],
        },
        "tax_compile_" + year,
    )
    try:
        policy = json.loads(record["response"]["policy_json"])
        failures = acceptance(policy, year)
        if failures:
            raise ValueError(f"Compilation rejected: {len(failures)} incorrect fixture answers")
    except (ValueError, TypeError, KeyError) as exc:
        raise ModelOutputError(str(exc), record) from None
    path = ROOT / f"artifacts/candidates/gemini_{year}.json"
    write_json(path, policy)
    write_json(
        path.with_suffix(".review.json"),
        {
            "sha256": digest(path),
            "automated_acceptance": "passed",
            "human_review": "pending",
            "request_sha256": record["request_sha256"],
        },
    )
    return record


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--year", choices=["2024-25", "2025-26"], required=True)
    args = parser.parse_args()
    compile_with_gemini(args.year, Gemini(live=True))
