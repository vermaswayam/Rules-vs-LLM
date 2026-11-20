"""Rules, distribution checks and text review expose the same alert interface."""

from collections import defaultdict
from difflib import SequenceMatcher
import hashlib
import json
import math
import re
from .data import timestamp
from .reference import tokens

EMAIL = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.I)
PHONE = re.compile(r"(?<!\d)(?:\+1[ .-]?)?\(?[2-9]\d{2}\)?[ .-]\d{3}[ .-]\d{4}(?!\d)")
NAME = re.compile(
    r"\b(?i:caller name|contact name|my name is)\s*:?\s*[A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,2}"
)


def pii_evidence(text):
    found = []
    for label, pattern in [("email", EMAIL), ("phone", PHONE), ("explicit_name", NAME)]:
        if pattern.search(text):
            found.append(label)
    return found


def fingerprint(row):
    return json.dumps(row, sort_keys=True, ensure_ascii=True)


def detect(rows, reference, family="rule"):
    if family not in ["rule", "statistical"]:
        raise ValueError("Use review_with_llm for actual model reviews")
    alerts = []

    def alert(problem, index, why, score=1.0, severity="warning"):
        # Examples are keys and explanations, not leaked free-text payloads.
        alerts.append(
            {
                "problem": problem,
                "row_index": index,
                "unique_key": rows[index].get("unique_key"),
                "family": family,
                "reason": why,
                "score": round(score, 6),
                "severity": severity,
            }
        )

    seen, near = {}, defaultdict(list)
    agency_batch = defaultdict(list)
    for i, row in enumerate(rows):
        missing = reference.columns - set(row)
        if missing:
            alert(
                "schema_change",
                i,
                "Missing contract columns: " + ", ".join(sorted(missing)),
                severity="error",
            )
        if family == "rule":
            bad_types = [
                k
                for k in ["latitude", "longitude"]
                if row.get(k) is not None and type(row[k]) is not float
            ]
        else:
            bad_types = [
                k
                for k, value in row.items()
                if value is not None
                and k in reference.expected_types
                and type(value).__name__ != reference.expected_types[k]
            ]
        if bad_types:
            alert(
                "type_change",
                i,
                "Observed type differs from "
                + ("declared numeric contract: " if family == "rule" else "training modal type: ")
                + ", ".join(bad_types),
                severity="error",
            )
        created, closed = timestamp(row.get("created_date")), timestamp(row.get("closed_date"))
        date = row.get("created_date")
        bad_date = (
            bool(date and not created)
            if family == "rule"
            else bool(date and re.sub(r"\d", "D", str(date)) not in reference.date_shapes)
        )
        if bad_date:
            alert(
                "date_format",
                i,
                (
                    "Created date does not match ISO contract"
                    if family == "rule"
                    else "Date-format signature was unseen in training"
                ),
                severity="error",
            )
        if created and closed:
            duration = (closed - created).total_seconds()
            if (family == "rule" and duration < 0) or (
                family == "statistical" and duration < reference.minimum_duration
            ):
                alert(
                    "negative_duration",
                    i,
                    (
                        "Closed date precedes created date"
                        if family == "rule"
                        else f"Duration {duration:g}s below training support minimum {reference.minimum_duration:g}s"
                    ),
                    severity="error",
                )
        lat, lon = row.get("latitude"), row.get("longitude")
        if type(lat) is float and type(lon) is float:
            if family == "rule":
                bad = not (40 <= lat <= 41.1 and -74.3 <= lon <= -73.6) and (
                    40 <= lon <= 41.1 and -74.3 <= lat <= -73.6
                )
                score = 1.0
            else:
                lat_mid, lat_mad = reference.geo["latitude"]
                lon_mid, lon_mad = reference.geo["longitude"]
                score = max(abs(lat - lat_mid) / lat_mad, abs(lon - lon_mid) / lon_mad)
                bad = score > 20
            if bad:
                alert(
                    "coordinates_swapped",
                    i,
                    (
                        "Coordinates fit reverse NYC bounding box"
                        if family == "rule"
                        else "Robust coordinate distance exceeds 20 training MADs"
                    ),
                    score,
                    "error",
                )
        signature = fingerprint(row)
        # Statistical baseline uses a hash collision-frequency check, not a second
        # copy of hand-coded domain knowledge. Exact identity is a degenerate case.
        signature = (
            hashlib.sha256(signature.encode()).hexdigest() if family == "statistical" else signature
        )
        if signature in seen:
            alert(
                "exact_duplicate",
                i,
                f"Identical normalized row already observed at index {seen[signature]}",
                severity="error",
            )
        else:
            seen[signature] = i
        key = (row.get("agency"), row.get("complaint_type"), row.get("incident_address"))
        if key[2] and created:
            # Blocking avoids quadratic comparison across an entire day/customer.
            for j, previous in near[key][-25:]:
                earlier = timestamp(previous.get("created_date"))
                distance = abs((created - earlier).total_seconds())
                if distance <= (30 if family == "rule" else 120):
                    a = str(row.get("descriptor") or "").lower().strip(" .")
                    b = str(previous.get("descriptor") or "").lower().strip(" .")
                    similarity = (
                        float(a == b) if family == "rule" else SequenceMatcher(None, a, b).ratio()
                    )
                    if signature != (
                        hashlib.sha256(fingerprint(previous).encode()).hexdigest()
                        if family == "statistical"
                        else fingerprint(previous)
                    ) and similarity >= (1 if family == "rule" else 0.88):
                        alert(
                            "near_duplicate",
                            i,
                            f"Same agency/problem/address as index {j}, {distance:g}s apart; text similarity {similarity:.3f}",
                            similarity,
                        )
                        break
            near[key].append((i, row))
        agency_batch[row.get("agency")].append(i)
        zip_, borough = row.get("incident_zip"), row.get("borough")
        if zip_ in reference.zip_boroughs and borough not in [None, "", "Unspecified"]:
            count = reference.zip_pairs[zip_, borough]
            total = reference.zips[zip_]
            probability = (count + 1) / (total + 5)
            if (family == "rule" and borough not in reference.zip_boroughs[zip_]) or (
                family == "statistical" and total >= 10 and probability < 0.03
            ):
                alert(
                    "zip_borough",
                    i,
                    (
                        "Borough absent from training ZIP relation"
                        if family == "rule"
                        else f"Conditional borough probability {probability:.4f} below .03; support {total}"
                    ),
                    1 - probability,
                )
        c, d = row.get("complaint_type"), row.get("descriptor")
        if c in reference.descriptors and d and d in reference.all_descriptors:
            probability = (reference.pairs[c, d] + 1) / (
                reference.complaints[c] + len(reference.descriptors[c]) + 1
            )
            bad = (
                d not in reference.descriptors[c]
                if family == "rule"
                else reference.complaints[c] >= 20 and probability < 0.005
            )
            if bad:
                alert(
                    "complaint_descriptor",
                    i,
                    (
                        "Known descriptor unseen for this complaint type"
                        if family == "rule"
                        else f"Conditional descriptor probability {probability:.5f} below .005"
                    ),
                    1 - probability,
                )
        resolution = str(row.get("resolution_description") or "")
        status = str(row.get("status") or "")
        if family == "rule":
            lower = resolution.lower()
            contradiction = (
                status == "Closed" and ("remains pending" in lower or "not been resolved" in lower)
            ) or (
                status in ["Open", "Pending", "Assigned"]
                and ("case is now closed" in lower or "case has been closed" in lower)
            )
            if contradiction:
                alert(
                    "resolution_status",
                    i,
                    "Explicit completion/pending phrase conflicts with status; workflow review required",
                )
            evidence = pii_evidence(str(row.get("descriptor") or "") + " " + resolution)
            if evidence:
                alert(
                    "personal_data",
                    i,
                    "Potential personal data patterns: " + ", ".join(evidence),
                    severity="error",
                )
        else:
            if resolution and status in reference.status_counts:
                scores = {
                    s: reference.status_score(resolution, s)
                    for s in reference.status_counts
                    if reference.status_counts[s] >= 20
                }
                if scores:
                    best = max(scores, key=scores.get)
                    gap = scores[best] - scores.get(status, scores[best])
                    if best != status and gap > 8:
                        alert(
                            "resolution_status",
                            i,
                            f"Token likelihood favours {best} over {status}; log-score gap {gap:.2f}",
                            gap,
                        )
            text = str(row.get("descriptor") or "") + " " + resolution
            # Lightweight token anomaly baseline; intentionally not a disguised LLM.
            rare_contact_tokens = sum(
                1 for token in tokens(text) if token not in reference.all_tokens
            )
            contact_shape = bool(EMAIL.search(text) or PHONE.search(text))
            if contact_shape or (
                rare_contact_tokens >= 3
                and re.search(r"\b(name|resident|caller|callback)\b", text, re.I)
            ):
                alert(
                    "personal_data",
                    i,
                    f"Contact shape or unusual contact vocabulary ({rare_contact_tokens} unseen tokens)",
                )
    for agency, indices in agency_batch.items():
        null_indices = [i for i in indices if rows[i].get("descriptor") is None]
        baseline_null, baseline_n = reference.agency_nulls[agency]
        if not baseline_n or len(indices) < 10:
            continue
        baseline = baseline_null / baseline_n
        observed = len(null_indices) / len(indices)
        if family == "rule":
            bad, score = observed > baseline + 0.10, observed - baseline
            reason = f"{agency} descriptor-null rate {observed:.3f} vs training {baseline:.3f}; increase >10pp"
        else:
            # Two-proportion uncertainty includes finite training support.
            smoothed = (baseline_null + 1) / (baseline_n + 2)
            stderr = math.sqrt(smoothed * (1 - smoothed) * (1 / len(indices) + 1 / baseline_n))
            score = (observed - baseline) / max(stderr, 1e-9)
            bad = score > 4 and observed - baseline > 0.02
            reason = (
                f"{agency} descriptor-null shift z={score:.2f}, increase {observed-baseline:.3f}"
            )
        if bad:
            for i in null_indices:
                alert("agency_null_spike", i, reason, score)
    return alerts
