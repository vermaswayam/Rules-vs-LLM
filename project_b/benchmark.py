"""Controlled injections, unlabelled holdout controls, matched sampled LLM cohort.

We do not call every real control-row alert a confirmed false alarm: semantic
ground truth is unavailable. Reports preserve this important limitation.
"""

import random
import time
from common.io import ROOT, write_json, read_json
from common.gemini import GeminiUnavailable, ModelOutputError
from .data import load_split, structural_controls, profile_raw, PROBLEMS
from .reference import Reference
from .injector import inject
from .detectors import detect
from .llm_review import review_with_llm
from .hybrid import run_hybrid

CPU_USD_PER_HOUR = 0.04
SEEDS = [17, 29, 44]
RATES = [0.01, 0.05, 0.10]


def wilson(successes, total):
    if not total:
        return [None, None]
    z = 1.96
    p = successes / total
    center = (p + z * z / (2 * total)) / (1 + z * z / total)
    half = z * ((p * (1 - p) / total + z * z / (4 * total * total)) ** 0.5) / (1 + z * z / total)
    return [max(0, center - half), min(1, center + half)]


def evaluate(alerts, problem, positive, n):
    predicted = {a["row_index"] for a in alerts if a["problem"] == problem}
    tp = len(predicted & positive)
    fp = len(predicted - positive)
    return {
        "tp": tp,
        "fn": len(positive) - tp,
        "fp_on_noninjected_rows": fp,
        "positive_rows": len(positive),
        "negative_rows": n - len(positive),
        "recall": tp / len(positive) if positive else None,
    }


def _call(rows, reference, family):
    if family == "hybrid":
        result = run_hybrid(rows, reference)
        return result["alerts"], result
    return detect(rows, reference, family), None


def measured_review(rows, reference, client, experiment):
    try:
        alerts, record = review_with_llm(rows, reference, client, experiment)
        return alerts, record, None
    except ModelOutputError as exc:
        # Invalid output is a real model failure, not unavailable credentials.
        return [], exc.record, str(exc)


def prepare_inputs(rows_limit=1200, llm_rows=64):
    raw, train, holdout = load_split()
    reference = Reference(train)
    controls = structural_controls(holdout)
    controls = random.Random(101).sample(controls, min(rows_limit, len(controls)))
    cohort = random.Random(909).sample(controls, min(llm_rows, len(controls)))
    return raw, train, holdout, reference, controls, cohort


def mixed_batch(controls, reference):
    rows, truth = [], {}
    segment = max(1, len(controls)//len(PROBLEMS))
    for index, problem in enumerate(PROBLEMS):
        subset = controls[index*segment:(index+1)*segment]
        batch = inject(subset, problem, .1, 100+index, reference)
        offset = len(rows)
        rows.extend(batch['rows'])
        truth[problem] = {offset+i for i in batch['positive_indices']}
    return rows, truth


def run(client, rows_limit=1200, llm_rows=64):
    raw, train, holdout, reference, controls, cohort = prepare_inputs(rows_limit, llm_rows)
    profile = profile_raw(raw)
    write_json(ROOT / "artifacts/raw_profile.json", profile)
    details, summary, examples = [], [], []
    control_records = {}
    for family in ["rule", "statistical", "hybrid"]:
        start_cpu, start = time.process_time(), time.perf_counter()
        clean_alerts, _ = _call(controls, reference, family)
        control_records[family] = {
            "wall_seconds": time.perf_counter() - start,
            "cpu_seconds": time.process_time() - start_cpu,
            "alerts": clean_alerts,
        }
    for problem in PROBLEMS:
        print("Benchmarking " + problem, flush=True)
        for family in ["rule", "statistical", "hybrid"]:
            trials = []
            for rate in RATES:
                for seed in SEEDS:
                    batch = inject(controls, problem, rate, seed, reference)
                    start_cpu, start = time.process_time(), time.perf_counter()
                    alerts, hybrid = _call(batch["rows"], reference, family)
                    elapsed, cpu = time.perf_counter() - start, time.process_time() - start_cpu
                    result = evaluate(
                        alerts, problem, batch["positive_indices"], len(batch["rows"])
                    )
                    result.update(
                        {
                            "problem": problem,
                            "family": family,
                            "seed": seed,
                            "requested_rate": rate,
                            "actual_rate": batch["actual_rate"],
                            "unit": batch["unit"],
                            "rows": len(batch["rows"]),
                            "wall_seconds": elapsed,
                            "cpu_seconds": cpu,
                            "candidate_rows": hybrid["candidate_rows"] if hybrid else None,
                            "reviewed_rows": 0,
                        }
                    )
                    details.append(result)
                    trials.append(result)
                    if rate == 0.05 and seed == SEEDS[0]:
                        examples.extend(
                            a
                            for a in alerts
                            if a["problem"] == problem
                            and a["row_index"] in batch["positive_indices"]
                        )
            tp, positive = sum(t["tp"] for t in trials), sum(t["positive_rows"] for t in trials)
            total_rows, wall, cpu = (
                sum(t["rows"] for t in trials),
                sum(t["wall_seconds"] for t in trials),
                sum(t["cpu_seconds"] for t in trials),
            )
            clean_predicted = {
                a["row_index"] for a in control_records[family]["alerts"] if a["problem"] == problem
            }
            summary.append(
                {
                    "problem": problem,
                    "family": family,
                    "trials": len(trials),
                    "detected_rows": tp,
                    "injected_rows": positive,
                    "recall": tp / positive if positive else None,
                    "recall_wilson_95": wilson(tp, positive),
                    "batch_detection_rate": sum(t["tp"] > 0 for t in trials) / len(trials),
                    "control_alerts": len(clean_predicted),
                    "control_rows": len(controls),
                    "control_alert_rate_proxy_far": len(clean_predicted) / len(controls),
                    "control_rate_wilson_95": wilson(len(clean_predicted), len(controls)),
                    "throughput_rows_second": total_rows / wall,
                    "cpu_seconds_per_million": cpu / total_rows * 1e6,
                    "cpu_scenario_usd_per_million": cpu
                    / total_rows
                    * 1e6
                    / 3600
                    * CPU_USD_PER_HOUR,
                    "llm_invoice_usd_per_million": 0,
                    "explanation": (
                        "Concrete row/batch predicate and support counts"
                        if family != "hybrid"
                        else "Accepted hard checks; semantic alerts deferred when no model evidence exists"
                    ),
                }
            )
    # Blinded cohort selected before corruption. All families see the SAME rows.
    llm_summary, llm_errors = [], []
    matched = []
    try:
        clean_model_alerts, clean_record, clean_error = measured_review(
            cohort, reference, client, "dq_control"
        )
        if clean_error:
            llm_errors.append("Control review rejected: " + clean_error)
        for problem in PROBLEMS:
            batch = inject(cohort, problem, 0.1, 71, reference)
            alerts, record, output_error = measured_review(
                batch["rows"], reference, client, "dq_" + problem
            )
            score = evaluate(alerts, problem, batch["positive_indices"], len(batch["rows"]))
            clean_predicted = {
                a["row_index"] for a in clean_model_alerts if a["problem"] == problem
            }
            llm_summary.append(
                {
                    "problem": problem,
                    "family": "llm",
                    **score,
                    "control_alert_rate_proxy_far": (
                        len(clean_predicted) / len(cohort) if not clean_error else None
                    ),
                    "output_contract_error": output_error,
                    "control_output_contract_error": clean_error,
                    "control_rows": len(cohort),
                    "throughput_rows_second": len(batch["rows"]) / record["latency_seconds"],
                    "paid_usd_per_million": record["projected_paid_usd"] / len(batch["rows"]) * 1e6,
                    "latency_seconds": record["latency_seconds"],
                    "request_sha256": record["request_sha256"],
                    "usage": record["usage"],
                    "review_scope": f"Matched {len(cohort)}-row cohort, 10% injection, one seed; text truncated at 700 chars",
                }
            )
            for family in ["rule", "statistical", "hybrid"]:
                subset_alerts, _ = _call(batch["rows"], reference, family)
                matched.append(
                    {
                        "problem": problem,
                        "family": family,
                        **evaluate(
                            subset_alerts, problem, batch["positive_indices"], len(batch["rows"])
                        ),
                    }
                )
    except (GeminiUnavailable, ValueError) as exc:
        llm_errors.append(str(exc))
    # A mixed batch: independent segments prevent one corruption erasing another.
    mixed_rows, mixed_truth = mixed_batch(controls, reference)
    start = time.perf_counter()
    hybrid_model_error = None
    try:
        mixed = run_hybrid(mixed_rows, reference, client=client)
    except ModelOutputError as exc:
        hybrid_model_error = str(exc)
        mixed = run_hybrid(mixed_rows, reference)
        # The response is unusable but its tokens and latency were real. Preserve
        # its cost while leaving every unadjudicated candidate in the queue.
        mixed['records'] = [exc.record]
        mixed['attempted_review_rows'] = min(mixed['candidate_rows'], mixed['review_budget'])
    except (GeminiUnavailable, ValueError) as exc:
        hybrid_model_error = str(exc)
        mixed = run_hybrid(mixed_rows, reference)
    elapsed = time.perf_counter() - start
    mixed_scores = [
        dict(problem=p, **evaluate(mixed["alerts"], p, labels, len(mixed_rows)))
        for p, labels in mixed_truth.items()
    ]
    result = {
        "dataset_manifest": read_json(ROOT / "data/nyc/manifest.json"),
        "split": {
            "train": len(train),
            "holdout": len(holdout),
            "structurally_valid_holdout": len(structural_controls(holdout)),
            "benchmark_control_rows": len(controls),
            "method": "SHA256(unique_key) mod10 <6 train, else holdout; fixed random sample of holdout",
        },
        "seeds": SEEDS,
        "rates": RATES,
        "summary": summary,
        "llm_summary": llm_summary,
        "llm_errors": llm_errors,
        "matched_llm_cohort_deterministic": matched,
        "llm_status": (
            "measured" if len(llm_summary) == 12 else "partial" if llm_summary else "not_measured"
        ),
        "mixed_hybrid": {
            "rows": len(mixed_rows),
            "wall_seconds": elapsed,
            "throughput_rows_second": len(mixed_rows) / elapsed,
            "candidate_rows": mixed["candidate_rows"],
            "reviewed_rows": mixed["reviewed_rows"],
            "deferred_rows": mixed["deferred_rows"],
            "scores": mixed_scores,
            "llm_invoice_usd": 0,
        },
        "profile": profile,
        "cpu_usd_per_core_hour_scenario": CPU_USD_PER_HOUR,
        "metric_limitations": [
            "Control rows have structural screening, not exhaustive human semantic labels: control alert rate is a proxy, not certified false-alarm rate.",
            "Rows in agency null-spike events are correlated; Wilson intervals are descriptive and not independent-event confidence guarantees.",
            "Monthly first-key/time slices are not representative random samples of all NYC 2023 data.",
            "Injection variants are limited; tuning on these templates would overstate generalization.",
            "Throughput includes complete detector-family execution, not an isolated single check; repeated per-problem rows share that family cost.",
        ],
    }
    result["llm_cohort_rows"] = len(cohort)
    result["mixed_hybrid"]["model_error"] = hybrid_model_error
    result['mixed_hybrid']['review_status'] = ('rejected_output' if hybrid_model_error and mixed['records'] else 'measured' if mixed['records'] else 'not_measured')
    result['mixed_hybrid']['attempted_review_rows'] = mixed.get('attempted_review_rows',mixed['reviewed_rows'])
    result["mixed_hybrid"]["model_records"] = [
        {
            "request_sha256": r["request_sha256"],
            "paid_usd": r["projected_paid_usd"],
            "latency_seconds": r["latency_seconds"],
        }
        for r in mixed["records"]
    ]
    result["mixed_hybrid"]["projected_paid_usd"] = sum(
        r["projected_paid_usd"] for r in mixed["records"]
    )
    write_json(ROOT / "artifacts/metrics_b.json", result)
    write_json(ROOT / "artifacts/dq_trial_results.json", details)
    write_json(ROOT / "artifacts/dq_alert_examples.json", examples[:250])
    write_json(
        ROOT / "artifacts/control_alerts.json", {k: v["alerts"] for k, v in control_records.items()}
    )
    return result
