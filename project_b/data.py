"""Keep source bytes unchanged; normalization is explicit and separately measured."""

from collections import Counter
from datetime import datetime
import hashlib
from common.io import ROOT, read_json

COLUMNS = [
    "unique_key",
    "created_date",
    "closed_date",
    "agency",
    "complaint_type",
    "descriptor",
    "resolution_description",
    "status",
    "incident_zip",
    "borough",
    "latitude",
    "longitude",
    "incident_address",
]
PROBLEMS = [
    "schema_change",
    "type_change",
    "date_format",
    "coordinates_swapped",
    "exact_duplicate",
    "near_duplicate",
    "agency_null_spike",
    "negative_duration",
    "zip_borough",
    "complaint_descriptor",
    "resolution_status",
    "personal_data",
]


def timestamp(value):
    if not isinstance(value, str):
        return None
    try:
        return datetime.fromisoformat(value) if "T" in value else None
    except ValueError:
        return None


def normalize(row):
    result = {column: row.get(column) for column in COLUMNS}
    # Socrata serializes numeric API fields as strings. Convert once at ingestion;
    # the injected type change is a violation of this normalized contract.
    for field in ["latitude", "longitude"]:
        if result[field] is not None:
            try:
                result[field] = float(result[field])
            except (TypeError, ValueError):
                pass
    return result


def load_split():
    raw = read_json(ROOT / "data/nyc/raw_2023.json")
    train, test = [], []
    for row in raw:
        normalized = normalize(row)
        bucket = int(hashlib.sha256(str(row["unique_key"]).encode()).hexdigest()[:8], 16) % 10
        (train if bucket < 6 else test).append(normalized)
    return raw, train, test


def structural_controls(rows):
    """Exclude hard pre-existing failures; do not erase unusual semantic values.

    These are UNLABELLED controls, not a claim of human-certified clean data.
    """
    result, seen = [], set()
    for row in rows:
        created, closed = timestamp(row.get("created_date")), timestamp(row.get("closed_date"))
        if (
            not created
            or created.year != 2023
            or not row.get("agency")
            or not row.get("unique_key")
        ):
            continue
        if closed and closed < created:
            continue
        if row["unique_key"] in seen:
            continue
        seen.add(row["unique_key"])
        lat, lon = row.get("latitude"), row.get("longitude")
        if lat is not None and (not isinstance(lat, (int, float)) or not 40 <= lat <= 41.1):
            continue
        if lon is not None and (not isinstance(lon, (int, float)) or not -74.3 <= lon <= -73.6):
            continue
        result.append(row)
    return result


def profile_raw(raw):
    """Observations have different meanings; a missing closed date is not an error."""
    issues = {}

    def collect(name, indices, interpretation):
        indices = list(indices)
        issues[name] = {
            "count": len(indices),
            "example_keys": [raw[i].get("unique_key") for i in indices[:5]],
            "interpretation": interpretation,
        }

    for field in COLUMNS:
        collect(
            "missing_" + field,
            (i for i, r in enumerate(raw) if r.get(field) in [None, ""]),
            "Completeness observation; validity depends on agency/workflow, not automatically corruption",
        )
    collect(
        "closed_before_created",
        (
            i
            for i, r in enumerate(raw)
            if timestamp(r.get("closed_date"))
            and timestamp(r.get("created_date"))
            and timestamp(r["closed_date"]) < timestamp(r["created_date"])
        ),
        "Hard chronology failure",
    )
    collect(
        "mojibake_text",
        (
            i
            for i, r in enumerate(raw)
            if any(
                token in str(r.get("resolution_description", "")) for token in ["â\x80", "Ã", "â€™"]
            )
        ),
        "Encoding artifact in published text; raw bytes retained",
    )
    collect(
        "closed_status_without_closed_date",
        (i for i, r in enumerate(raw) if r.get("status") == "Closed" and not r.get("closed_date")),
        "Workflow inconsistency candidate; agency confirmation needed",
    )
    seen = set()
    duplicate_ids = []
    for i, row in enumerate(raw):
        if row.get("unique_key") in seen:
            duplicate_ids.append(i)
        seen.add(row.get("unique_key"))
    collect("repeated_unique_key", duplicate_ids, "Potential ingestion duplication")
    collect(
        "unassigned_borough",
        (i for i, r in enumerate(raw) if r.get("borough") in [None, "", "Unspecified"]),
        "Unknown geography; retain as unknown rather than inventing a borough",
    )
    return {
        "rows": len(raw),
        "agency_counts": dict(Counter(r.get("agency") for r in raw)),
        "month_counts": dict(sorted(Counter(r["created_date"][:7] for r in raw).items())),
        "issues": issues,
        "scope": "Counts describe the saved monthly coverage sample only; not the entire 2023 population",
    }
