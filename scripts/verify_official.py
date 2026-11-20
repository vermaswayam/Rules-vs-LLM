"""Replay checks against raw official output, keeping its rupee-rounded value too."""

from decimal import Decimal, ROUND_HALF_UP
import hashlib
import json
from common.io import ROOT, read_json, write_json, digest


def verify():
    folder = ROOT / "data/official_calculator"
    inputs, output = read_json(folder / "check_inputs.json"), read_json(
        folder / "check_outputs.json"
    )
    canonical = json.dumps(inputs, separators=(",", ":"), ensure_ascii=False)
    if hashlib.sha256(canonical.encode()).hexdigest() != output["inputs_sha256"]:
        raise ValueError("Official input/output evidence binding does not match")
    if digest(folder / "calculator.js") != output["official_asset_sha256"]:
        raise ValueError("Official asset hash mismatch")
    if len(inputs) != len(output["outputs"]):
        raise ValueError("Incomplete official output set")
    checks_path = ROOT / "project_a/tests/fixtures/official_checks.json"
    checks = read_json(checks_path)
    indexed = {c["case_id"]: c for c in checks}
    for call, result in zip(inputs, output["outputs"]):
        check = indexed[call["case_id"]]
        net = max(0, check["input"]["salary"] - (50000 if call["regime"] == "old" else 75000))
        if (
            net != call["net_taxable_income"]
            or call["assessment_year"] != "2025-26"
            or call["age"] != check["input"]["age"]
            or call["resident"] != check["input"]["resident"]
        ):
            raise ValueError("Official call parameters differ from labelled profile")
        raw = result["totalTaxLiability"]
        rounded = int((Decimal(raw) / 10).quantize(Decimal(1), rounding=ROUND_HALF_UP)) * 10
        check["official_" + call["regime"]] = rounded
        check["official_" + call["regime"] + "_raw_display"] = raw
        check["evidence"] = "data/official_calculator/check_outputs.json"
        check["evidence_sha256"] = digest(folder / "check_outputs.json")
        check["validation_method"] = (
            "Official deployed calculator calculation functions, executed unchanged in isolated Node VM; wrapper selects UI state and captures result. Final display converted with s288B."
        )
    for check in checks:
        if type(check["official_old"]) is int and type(check["official_new"]) is int:
            check["status"] = "verified"
    write_json(checks_path, checks)
    return checks


if __name__ == "__main__":
    checks = verify()
    print(f"Replayed {sum(c['status']=='verified' for c in checks)} official-calculator profiles")
