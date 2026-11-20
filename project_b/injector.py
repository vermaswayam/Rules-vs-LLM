"""Seeded mutations with a sidecar label set that detectors never receive."""

from collections import Counter
from copy import deepcopy
from datetime import timedelta
import random
from .data import PROBLEMS, timestamp


def inject(clean, problem, rate=0.05, seed=2026, reference=None):
    if problem not in PROBLEMS or not 0 <= rate <= 1 or not clean:
        raise ValueError("Unknown corruption, invalid rate or empty batch")
    rows = deepcopy(clean)
    rng = random.Random(seed)
    requested = round(len(rows) * rate)
    eligible = list(range(len(rows)))
    if problem == "coordinates_swapped" or problem == "type_change":
        eligible = [
            i
            for i, r in enumerate(rows)
            if type(r.get("latitude")) is float and type(r.get("longitude")) is float
        ]
    elif problem == "negative_duration":
        eligible = [i for i, r in enumerate(rows) if timestamp(r.get("created_date"))]
    elif problem == "zip_borough":
        eligible = [
            i
            for i, r in enumerate(rows)
            if reference and r.get("incident_zip") in reference.zip_boroughs
        ]
    elif problem == "complaint_descriptor":
        eligible = [
            i
            for i, r in enumerate(rows)
            if reference
            and r.get("complaint_type") in reference.descriptors
            and any(
                c != r["complaint_type"] and values - reference.descriptors[r["complaint_type"]]
                for c, values in reference.descriptors.items()
            )
        ]
    elif problem == "near_duplicate":
        eligible = [
            i
            for i, r in enumerate(rows)
            if r.get("incident_address") and timestamp(r.get("created_date"))
        ]
    elif problem == "agency_null_spike":
        agency = Counter(r.get("agency") for r in rows).most_common(1)[0][0]
        eligible = [
            i
            for i, r in enumerate(rows)
            if r.get("agency") == agency and r.get("descriptor") is not None
        ]
    count = min(requested, len(eligible))
    chosen = sorted(rng.sample(eligible, count))
    if problem == "schema_change":
        # A dropped column affects the whole batch; rate is an event switch here.
        chosen = list(range(len(rows))) if requested else []
    if problem == "date_format":
        # A contiguous mid-batch segment models a producer deployment, not IID noise.
        start = len(rows) // 2
        chosen = list(range(start, min(len(rows), start + count)))
    positives = set(chosen)
    originals = []
    for serial, i in enumerate(chosen):
        row = rows[i]
        if problem == "schema_change":
            if seed % 2:
                row["problem"] = row.pop("complaint_type")
            else:
                del row["complaint_type"]
        elif problem == "type_change":
            row["latitude"] = str(row["latitude"])
        elif problem == "date_format":
            row["created_date"] = timestamp(row["created_date"]).strftime("%d/%m/%Y %H:%M:%S")
        elif problem == "coordinates_swapped":
            row["latitude"], row["longitude"] = row["longitude"], row["latitude"]
        elif problem in ["exact_duplicate", "near_duplicate"]:
            duplicate = deepcopy(row)
            if problem == "near_duplicate":
                duplicate["unique_key"] = f"near-{seed}-{serial}"
                duplicate["created_date"] = (
                    timestamp(row["created_date"]) + timedelta(seconds=rng.choice([1, 2, 7, 15]))
                ).isoformat(timespec="milliseconds")
                duplicate["descriptor"] = str(row.get("descriptor") or "") + rng.choice(
                    [" ", " .", "  "]
                )
            rows.append(duplicate)
            positives.remove(i)
            positives.add(len(rows) - 1)
            originals.append(i)
        elif problem == "agency_null_spike":
            row["descriptor"] = None
        elif problem == "negative_duration":
            row["closed_date"] = (timestamp(row["created_date"]) - timedelta(hours=1)).isoformat(
                timespec="milliseconds"
            )
        elif problem == "zip_borough":
            incompatible = sorted(
                {"BRONX", "BROOKLYN", "MANHATTAN", "QUEENS", "STATEN ISLAND"}
                - reference.zip_boroughs[row["incident_zip"]]
            )
            row["borough"] = rng.choice(incompatible)
        elif problem == "complaint_descriptor":
            alternatives = sorted(
                set().union(
                    *(v for c, v in reference.descriptors.items() if c != row["complaint_type"])
                )
                - reference.descriptors[row["complaint_type"]]
            )
            row["descriptor"] = rng.choice(alternatives)
        elif problem == "resolution_status":
            # Two directions; phrasing differs from the detector's exact phrase rules.
            if serial % 2:
                row["status"] = "Closed"
                row["resolution_description"] = (
                    "The inspection remains pending and the issue has not been resolved."
                )
            else:
                row["status"] = "Open"
                row["resolution_description"] = (
                    "Repairs are complete; the issue was fixed and this case is now closed."
                )
        elif problem == "personal_data":
            # Entirely fictitious reserved domains and 555-01xx telephone numbers.
            payloads = [
                " Contact: test.person@example.invalid.",
                " Call 212-555-0107 for access.",
                " Caller name: Maya Example.",
                " The resident, Arun Sample, requested a callback.",
            ]
            row["descriptor"] = str(row.get("descriptor") or "") + payloads[serial % len(payloads)]
    return {
        "rows": rows,
        "positive_indices": positives,
        "original_indices": originals,
        "problem": problem,
        "requested_rate": rate,
        "actual_corrupt_rows": len(positives),
        "actual_rate": len(positives) / len(rows),
        "seed": seed,
        "unit": "batch event" if problem == "schema_change" else "row",
    }
