"""Download only the named public sources. Cached snapshots are used by reproduce.py."""

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
from urllib.parse import urlencode
from urllib.request import Request, urlopen
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from common.io import ROOT, digest, write_json

SOURCES = {
    "salary_2024.html": "https://www.incometax.gov.in/iec/foportal/help/individual/return-applicable-3",
    "salary_2025.html": "https://www.incometax.gov.in/iec/foportal/help/individual/return-applicable-1",
    "statute_2024_115bac.html": "https://www.incometaxindia.gov.in/hi/w/section-115bac-5",
    "statute_2025_115bac.html": "https://www.incometaxindia.gov.in/hi/w/section-115bac-6",
    "statute_2025_87a_amendment.html": "https://www.incometaxindia.gov.in/w/section-20-111",
    "statute_2024_87a.html": "https://www.incometaxindia.gov.in/w/section-87a-24",
    "finance_2025.pdf": "https://www.incometaxindia.gov.in/documents/20117/14614782/%E2%80%8BKey-Highlights-of-Finance-Act-2025.pdf/139e2679-ed0a-9470-7277-23d5d6244b9f?t=1767817038778",
    "calculator_manual.html": "https://www.incometax.gov.in/iec/foportal/help/all-topics/e-filing-services/income-tax-calculator-um",
}
FIELDS = "unique_key,created_date,closed_date,agency,complaint_type,descriptor,resolution_description,status,incident_zip,borough,latitude,longitude,incident_address"
API = "https://data.cityofnewyork.us/resource/erm2-nwe9.json"


def fetch(url):
    req = Request(
        url, headers={"User-Agent": "FireAI-assignment/1.0 (public research)", "Accept": "*/*"}
    )
    for attempt in range(3):
        try:
            with urlopen(req, timeout=40) as response:
                return response.read(), response.url
        except (TimeoutError, OSError):
            if attempt == 2:
                raise
            time.sleep(1)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--per-month", type=int, default=1000)
    parser.add_argument("--tax-only", action="store_true")
    args = parser.parse_args()
    folder = ROOT / "data/sources"
    folder.mkdir(parents=True, exist_ok=True)
    manifest_path = folder / "manifest.json"
    manifest = json.loads(manifest_path.read_text()) if manifest_path.exists() else {}
    for name, url in SOURCES.items():
        path = folder / name
        if not path.exists():
            try:
                body, final = fetch(url)
                path.write_bytes(body)
                manifest[name] = {
                    "url": url,
                    "final_url": final,
                    "sha256": digest(path),
                    "retrieved_at": datetime.now(timezone.utc).isoformat(),
                }
                write_json(manifest_path, manifest)
                print(f"Saved {name}: {len(body):,} bytes", flush=True)
            except Exception as exc:
                print(f"Could not fetch {name}: {type(exc).__name__}: {exc}", flush=True)
    if args.tax_only:
        return
    rows, queries = [], []
    for month in range(1, 13):
        start = f"2023-{month:02d}-01T00:00:00"
        end = f"2023-{month+1:02d}-01T00:00:00" if month < 12 else "2024-01-01T00:00:00"
        query = {
            "$select": FIELDS,
            "$where": f"created_date >= '{start}' AND created_date < '{end}'",
            "$order": "unique_key",
            "$limit": args.per_month,
        }
        url = API + "?" + urlencode(query)
        month_path = ROOT / f"data/nyc/month_{month:02d}.json"
        query_path = month_path.with_suffix(".query.json")
        if not month_path.exists():
            # Composite chronological ordering avoids slow key-only index scans.
            query["$order"] = "created_date,unique_key"
            url = API + "?" + urlencode(query)
            body, _ = fetch(url)
            write_json(month_path, json.loads(body))
            write_json(query_path, {"url": url})
        elif query_path.exists():
            url = json.loads(query_path.read_text(encoding="utf-8"))["url"]
        else:
            write_json(query_path, {"url": url})
        subset = json.loads(month_path.read_text(encoding="utf-8"))
        rows.extend(subset)
        queries.append(
            {"month": month, "url": url, "rows": len(subset), "sha256": digest(month_path)}
        )
        print(f"Month {month}: {len(subset):,} rows", flush=True)
    write_json(ROOT / "data/nyc/raw_2023.json", rows)
    count_url = (
        API
        + "?"
        + urlencode(
            {
                "$select": "count(*) as total",
                "$where": "created_date >= '2023-01-01T00:00:00' AND created_date < '2024-01-01T00:00:00'",
            }
        )
    )
    body, _ = fetch(count_url)
    write_json(
        ROOT / "data/nyc/manifest.json",
        {
            "dataset": API,
            "retrieved_at": datetime.now(timezone.utc).isoformat(),
            "sampling": "Monthly coverage slices sorted by each recorded query; NOT a random sample or census",
            "rows": len(rows),
            "population_query": count_url,
            "population": json.loads(body),
            "sha256": digest(ROOT / "data/nyc/raw_2023.json"),
            "queries": queries,
        },
    )


if __name__ == "__main__":
    main()
