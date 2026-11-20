"""Hard rules first; distribution/semantic candidates go into a bounded review queue."""

from .detectors import detect
from .llm_review import review_with_llm

RULE_WINNERS = {
    "schema_change",
    "type_change",
    "date_format",
    "coordinates_swapped",
    "exact_duplicate",
    "near_duplicate",
    "negative_duration",
}
STAT_WINNERS = {"agency_null_spike"}
REVIEW_PROBLEMS = {"zip_borough", "complaint_descriptor", "resolution_status", "personal_data"}


def run_hybrid(rows, reference, client=None, review_budget=32):
    rules = detect(rows, reference, "rule")
    stats = detect(rows, reference, "statistical")
    accepted = [a for a in rules if a["problem"] in RULE_WINNERS] + [
        a for a in stats if a["problem"] in STAT_WINNERS
    ]
    # Candidate queues have reasons; they are not silently reported as confirmed errors.
    candidates = [a for a in rules + stats if a["problem"] in REVIEW_PROBLEMS]
    # Surface semantic suspicions immediately, with an explicit review state.
    # A missing model must not make a suspicious row silently pass the dashboard gate.
    for candidate in candidates:
        accepted.append({**candidate, "triage_state": "needs_review", "severity": "warning"})
    unique_indices = sorted({a["row_index"] for a in candidates})
    reviewed_indices = unique_indices[:review_budget]
    records, llm_alerts = [], []
    if client is not None and reviewed_indices:
        subset = [rows[i] for i in reviewed_indices]
        llm_alerts, record = review_with_llm(subset, reference, client, "hybrid_review")
        records.append(record)
        for alert in llm_alerts:
            alert["row_index"] = reviewed_indices[alert["row_index"]]
        model_keys = {(a["problem"], a["row_index"]) for a in llm_alerts}
        for alert in accepted:
            if alert["row_index"] in reviewed_indices and alert["problem"] in REVIEW_PROBLEMS:
                alert["model_review"] = (
                    "supports_candidate"
                    if (alert["problem"], alert["row_index"]) in model_keys
                    else "does_not_support_candidate"
                )
        accepted.extend(llm_alerts)
    # Stable deduplication of rule, stat and model evidence.
    seen, result = set(), []
    for alert in accepted:
        key = (alert["problem"], alert["row_index"])
        if key not in seen:
            result.append(alert)
            seen.add(key)
    return {
        "alerts": result,
        "review_candidates": candidates,
        "candidate_rows": len(unique_indices),
        "reviewed_rows": len(reviewed_indices) if client else 0,
        "deferred_rows": len(unique_indices) - (len(reviewed_indices) if client else 0),
        "records": records,
        "review_budget": review_budget,
    }
