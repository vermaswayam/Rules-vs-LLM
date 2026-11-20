"""Accuracy, latency, genuine repeats and a controlled law-migration experiment."""

from collections import Counter
from copy import deepcopy
import hashlib
import json
from statistics import median
import time
from common.io import ROOT, read_json, write_json, digest
from common.gemini import GeminiUnavailable, ModelOutputError
from .models import TaxProfile
from .engine import compare
from .compiled import load_policy, acceptance, compile_with_gemini
from .llm_query import calculate_with_llm, rule_text
from .parser import parse_description
from .policy import hand_policy
from .cohort import comparison_cases, repeat_case as consistency_case

CORE_HOUR_USD = 0.04  # An explicit cloud CPU scenario, not laptop electricity/billing.


def percentile(values, p):
    return sorted(values)[min(len(values) - 1, int((len(values) - 1) * p))] if values else None


def run(client, live=False, live_limit=None):
    cases = read_json(ROOT / "project_a/tests/fixtures/tax_cases.json")
    methods = {}
    detailed = []
    for method in ["hand_rules", "compiled_codex"]:
        timings, failures, repeats, ledger_count = [], [], [], 0
        policies = (
            {year: load_policy(year) for year in ["2024-25", "2025-26"]}
            if method == "compiled_codex"
            else None
        )
        cpu_started = time.process_time()
        for case in cases:
            profile = TaxProfile.from_dict(case["input"])
            outputs = []
            # Actual calls, not ten reads of one cached return value.
            for repeat in range(10):
                start = time.perf_counter()
                answer = compare(profile, policies[profile.financial_year] if policies else None)
                timings.append(time.perf_counter() - start)
                outputs.append(
                    hashlib.sha256(json.dumps(answer, sort_keys=True).encode()).hexdigest()
                )
            actual = {r: answer[r]["tax_payable"] for r in ["old", "new"]}
            if actual != case["expected"]:
                failures.append(
                    {"case_id": case["id"], "expected": case["expected"], "actual": actual}
                )
            repeats.append(len(set(outputs)))
            ledger_count += int(
                all(line.get("clause") for r in ["old", "new"] for line in answer[r]["tax_ledger"])
            )
            detailed.append(
                {
                    "method": method,
                    "case_id": case["id"],
                    "actual": actual,
                    "expected": case["expected"],
                    "unique_answers_over_10": len(set(outputs)),
                }
            )
        cpu_seconds = time.process_time() - cpu_started
        methods[method] = {
            "status": "measured",
            "case_count": len(cases),
            "rupee_exact_both_regimes": (len(cases) - len(failures)) / len(cases),
            "failures": failures,
            "repeat_count": 10,
            "cases_with_identical_10_repeats": repeats.count(1),
            "latency_ms_median": median(timings) * 1000,
            "latency_ms_p95": percentile(timings, 0.95) * 1000,
            "measured_calls": len(timings),
            "cpu_seconds": cpu_seconds,
            "cpu_scenario_usd_per_1000": cpu_seconds / len(timings) * 1000 / 3600 * CORE_HOUR_USD,
            "llm_invoice_usd_per_1000": 0,
            "clause_ledger_fraction": ledger_count / len(cases),
            "policy_hashes": (
                {y: digest(ROOT / f"project_a/policies/compiled_{y}.json") for y in policies}
                if policies
                else None
            ),
        }
    descriptions = read_json(ROOT / "project_a/tests/fixtures/descriptions.json")
    parser_records = []
    for case in descriptions:
        result = parse_description(case["text"])
        correct = result["status"] == case["expected_status"] and all(
            result["fields"].get(k) == v for k, v in case["expected_fields"].items()
        )
        parser_records.append(
            {
                "case_id": case["id"],
                "correct": correct,
                "expected_status": case["expected_status"],
                **result,
            }
        )
    llm_records, errors = [], []
    selected = comparison_cases(cases, live_limit)
    unavailable = None
    for case in selected:
        try:
            record = calculate_with_llm(TaxProfile.from_dict(case["input"]), client)
            value = record["response"]
            llm_records.append(
                {
                    "case_id": case["id"],
                    "actual": {"old": value["old_tax"], "new": value["new_tax"]},
                    "expected": case["expected"],
                    "exact": value["old_tax"] == case["expected"]["old"]
                    and value["new_tax"] == case["expected"]["new"],
                    "latency_seconds": record["latency_seconds"],
                    "projected_paid_usd": record["projected_paid_usd"],
                    "usage": record["usage"],
                    "request_sha256": record["request_sha256"],
                }
            )
        except GeminiUnavailable as exc:
            unavailable = str(exc)
            if client.live:
                break
            continue  # Replay every available case, including responses after gaps.
        except (ValueError, KeyError) as exc:
            failed = getattr(exc, "record", {})
            errors.append(
                {
                    "case_id": case["id"],
                    "error": str(exc),
                    "latency_seconds": failed.get("latency_seconds"),
                    "projected_paid_usd": failed.get("projected_paid_usd"),
                    "request_sha256": failed.get("request_sha256"),
                }
            )
    repetitions = []
    available_ids = {record["case_id"] for record in llm_records} | {
        e["case_id"] for e in errors if "case_id" in e
    }
    if available_ids:
        repeat_case = consistency_case(cases)
        for index in range(10):
            try:
                record = calculate_with_llm(
                    TaxProfile.from_dict(repeat_case["input"]), client, repeat=index
                )
                repetitions.append(
                    {
                        "case_id": repeat_case["id"],
                        "old": record["response"]["old_tax"],
                        "new": record["response"]["new_tax"],
                        "request_sha256": record["request_sha256"],
                        "latency_seconds": record["latency_seconds"],
                    }
                )
            except ModelOutputError as exc:
                record = exc.record
                value = record["response"] if isinstance(record["response"], dict) else {}
                repetitions.append(
                    {
                        "case_id": repeat_case["id"],
                        "old": value.get("old_tax"),
                        "new": value.get("new_tax"),
                        "validation_error": str(exc),
                        "request_sha256": record["request_sha256"],
                        "latency_seconds": record["latency_seconds"],
                    }
                )
            except GeminiUnavailable as exc:
                errors.append({"stage": "repeat", "error": str(exc)})
                if client.live:
                    break
    invalid_cases = [e for e in errors if "case_id" in e]
    measured_cases = len(llm_records) + len(invalid_cases)
    timing_records = llm_records + [
        e for e in invalid_cases if e.get("latency_seconds") is not None
    ]
    methods["llm_query"] = {
        "status": (
            "measured"
            if measured_cases == len(selected) and unavailable is None
            else "partial" if measured_cases else "not_measured"
        ),
        "reason": unavailable,
        "selected_cases": len(selected),
        "measured_cases": measured_cases,
        "valid_cases": len(llm_records),
        "invalid_cases": len(invalid_cases),
        "accuracy_including_invalid_outputs": (
            sum(r["exact"] for r in llm_records) / measured_cases if measured_cases else None
        ),
        "errors": errors,
        "latency_ms_median": (
            median(r["latency_seconds"] * 1000 for r in timing_records) if timing_records else None
        ),
        "paid_usd_per_1000": (
            sum(r["projected_paid_usd"] for r in timing_records) / len(timing_records) * 1000
            if timing_records
            else None
        ),
        "repetitions": repetitions,
        "unique_answers_over_10": (
            len({json.dumps([r["old"], r["new"]], sort_keys=True) for r in repetitions})
            if len(repetitions) == 10
            else None
        ),
        "rupee_ledger_audit": "Model cites clauses in prose; no guaranteed reconciling ledger or verified clause-level arithmetic",
    }
    selected_ids = {c['id'] for c in selected}
    for method in ['hand_rules', 'compiled_codex']:
        paired = [r for r in detailed if r['method'] == method and r['case_id'] in selected_ids]
        methods[method]['comparison_cohort_cases'] = len(paired)
        methods[method]['comparison_cohort_accuracy'] = sum(r['actual'] == r['expected'] for r in paired)/len(paired)
    migration = migration_experiment(cases)
    migration["llm_stale_bundle_experiment"] = llm_migration_experiment(cases, client)
    compilation = {}
    for year in ["2024-25", "2025-26"]:
        try:
            record = compile_with_gemini(year, client)
            compilation[year] = {
                "status": "measured",
                "latency_seconds": record["latency_seconds"],
                "paid_usd": record["projected_paid_usd"],
                "request_sha256": record["request_sha256"],
                "human_review": "pending",
            }
        except ModelOutputError as exc:
            record = exc.record
            compilation[year] = {
                "status": "rejected",
                "reason": str(exc),
                "latency_seconds": record["latency_seconds"],
                "paid_usd": record["projected_paid_usd"],
                "request_sha256": record["request_sha256"],
            }
        except (GeminiUnavailable, ValueError, KeyError) as exc:
            compilation[year] = {"status": "not_measured", "reason": str(exc)}
    official = read_json(ROOT / "project_a/tests/fixtures/official_checks.json")
    verified = [
        c
        for c in official
        if c["status"] == "verified"
        and c.get("evidence")
        and type(c.get("official_old")) is int
        and type(c.get("official_new")) is int
    ]
    result = {
        "methods": methods,
        "parser": {
            "total": len(parser_records),
            "correct": sum(c["correct"] for c in parser_records),
            "records": parser_records,
            "response_distribution": dict(Counter(c["status"] for c in parser_records)),
        },
        "migration": migration,
        "gemini_compilation": compilation,
        "official_checks_verified": len(verified),
        "official_checks_pending": len(official) - len(verified),
        "official_mismatches": [
            c["case_id"]
            for c in verified
            if {"old": c["official_old"], "new": c["official_new"]} != c["engine_expected"]
        ],
        "cost_assumption_cpu_usd_per_hour": CORE_HOUR_USD,
        "compiled_provenance": "Codex-authored policy candidates, automated acceptance, no independent human approval claimed",
    }
    write_json(ROOT / "artifacts/metrics_a.json", result)
    write_json(ROOT / "artifacts/tax_case_results.json", detailed)
    write_json(ROOT / "artifacts/tax_llm_results.json", llm_records)
    return result


def migration_experiment(cases):
    new_cases = [c for c in cases if c["input"]["financial_year"] == "2025-26"]
    stale = hand_policy("2024-25")
    stale["financial_year"] = "2025-26"  # Deliberately simulate a missing/incorrect version guard.
    silent = []
    for case in new_cases:
        answer = compare(TaxProfile.from_dict(case["input"]), stale)
        if any(answer[r]["tax_payable"] != case["expected"][r] for r in ["old", "new"]):
            silent.append(case["id"])
    mutations = {}
    for component in ["new_slabs", "rebate_new_threshold", "rebate_new_cap"]:
        mutant = hand_policy("2025-26")
        mutant[component] = hand_policy("2024-25")[component]
        mutations[component] = len(acceptance(mutant, "2025-26"))
    measurements = {}
    for method in ["hand_rules", "compiled_codex"]:
        start = time.perf_counter()
        candidate = deepcopy(stale)
        updated = hand_policy("2025-26") if method == "hand_rules" else load_policy("2025-26")
        changed = [k for k in updated if candidate[k] != updated[k]]
        for key in changed:
            candidate[key] = deepcopy(updated[key])
        failures = acceptance(candidate, "2025-26")
        measurements[method] = {
            "patch_and_validation_seconds": time.perf_counter() - start,
            "changed_fields": changed,
            "remaining_failures": len(failures),
            "timing_scope": "Controlled in-memory patch plus full frozen-fixture validation; excludes original authoring, reading law and human review",
        }
    start = time.perf_counter()
    rule_text("2025-26")
    measurements["llm_query"] = {
        "bundle_load_seconds": time.perf_counter() - start,
        "live_accuracy_after_change": None,
        "timing_scope": "Prompt rule-bundle preparation only; not a model update/verification measurement",
    }
    return {
        "new_year_cases": len(new_cases),
        "stale_policy_silent_failures_without_guard": len(silent),
        "silent_failure_examples": silent[:10],
        "with_year_guard": "Rejected before calculation; covered by test",
        "one_field_mutation_wrong_regime_results": mutations,
        "measurements": measurements,
    }


def llm_migration_experiment(cases, client):
    """Compare genuine stale-bundle responses, never substitute the rule oracle."""
    new_cases = [c for c in cases if c["input"]["financial_year"] == "2025-26"]
    probes = new_cases[:: max(1, len(new_cases) // 5)][:5]
    results, error = [], None
    for case in probes:
        try:
            record = calculate_with_llm(
                TaxProfile.from_dict(case["input"]), client, rule_year="2024-25"
            )
            value = record["response"]
            results.append(
                {
                    "case_id": case["id"],
                    "silent_wrong": value["old_tax"] != case["expected"]["old"]
                    or value["new_tax"] != case["expected"]["new"],
                    "actual": {"old": value["old_tax"], "new": value["new_tax"]},
                    "expected": case["expected"],
                    "latency_seconds": record["latency_seconds"],
                    "request_sha256": record["request_sha256"],
                }
            )
        except ModelOutputError as exc:
            record = exc.record
            results.append({'case_id': case['id'], 'silent_wrong': False,
                            'invalid_output': True, 'validation_error': str(exc),
                            'expected': case['expected'], 'actual': record['response'],
                            'latency_seconds': record['latency_seconds'],
                            'request_sha256': record['request_sha256']})
        except (GeminiUnavailable, ValueError, KeyError) as exc:
            error = str(exc)
            break
    return {
        "status": (
            "measured" if len(results) == len(probes) else "partial" if results else "not_measured"
        ),
        "probe_count": len(probes),
        "results": results,
        "error": error,
    }
