"""One command: tests, fixed-data experiments, reports and evidence manifest."""

import argparse
from datetime import datetime, timezone
import platform
import subprocess
import sys
import time
import unittest
from common.io import ROOT, read_json, write_json, digest
from common.gemini import Gemini


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--live",
        action="store_true",
        help="Fill missing real Gemini evidence; cached calls are replayed and never billed again",
    )
    parser.add_argument(
        "--fetch",
        action="store_true",
        help="Fetch public sources before running; default uses saved, hashed snapshots",
    )
    parser.add_argument(
        "--live-limit",
        type=int,
        default=None,
        help="Optional smaller tax LLM cohort; default fixed stratified 200-profile cohort",
    )
    parser.add_argument("--rows", type=int, default=1200)
    parser.add_argument("--llm-rows", type=int, default=64)
    parser.add_argument(
        "--require-complete",
        action="store_true",
        help="Nonzero exit if external evidence requirements are unmet",
    )
    args = parser.parse_args()
    if (
        args.rows < 120
        or args.llm_rows < 16
        or (args.live_limit is not None and args.live_limit < 1)
    ):
        parser.error("rows>=120, llm-rows>=16 and live-limit>=1 required")
    if args.fetch:
        subprocess.run(
            [sys.executable, str(ROOT / "scripts/fetch_sources.py")], check=True, cwd=ROOT
        )
    started = time.perf_counter()
    manifest = read_json(ROOT / "data/nyc/manifest.json")
    if digest(ROOT / "data/nyc/raw_2023.json") != manifest["sha256"]:
        raise SystemExit("Raw data checksum mismatch; do not silently benchmark changed data")
    for name, source in read_json(ROOT / "data/sources/manifest.json").items():
        if digest(ROOT / "data/sources" / name) != source["sha256"]:
            raise SystemExit("Official source checksum mismatch: " + name)
    from scripts.verify_official import verify

    verify()
    suite = unittest.defaultTestLoader.discover(str(ROOT), pattern="test_*.py")
    tests = unittest.TextTestRunner(stream=sys.stdout, verbosity=1).run(suite)
    if not tests.wasSuccessful():
        raise SystemExit(1)
    client = Gemini(live=args.live)
    if args.live:
        from scripts.live_experiments import acquire
        acquire(client, rows_limit=args.rows, llm_rows=args.llm_rows, live_limit=args.live_limit)
        # Metrics replay the actual API responses; never count cache lookup time
        # as model latency or spend quota again while generating the reports.
        client.live = False
    from project_a.benchmark import run as run_a
    from project_b.benchmark import run as run_b

    print("Running Project A", flush=True)
    a = run_a(client, live=args.live, live_limit=args.live_limit)
    print("Running Project B", flush=True)
    b = run_b(client, rows_limit=args.rows, llm_rows=args.llm_rows)
    from scripts.render_reports import render

    render(a, b)
    pending = []
    if a["official_checks_verified"] < 30:
        pending.append("At least 30 evidenced official calculator checks")
    if (
        a["methods"]["llm_query"]["status"] != "measured"
        or a["methods"]["llm_query"]["measured_cases"] < 200
    ):
        pending.append("Full Gemini tax accuracy cohort")
    if len(a["methods"]["llm_query"]["repetitions"]) != 10:
        pending.append("Ten independently recorded tax-query responses")
    if any(v["status"] not in ["measured", "rejected"] for v in a["gemini_compilation"].values()):
        pending.append("Gemini compilation measurements for both financial years")
    if a["migration"]["llm_stale_bundle_experiment"]["status"] != "measured":
        pending.append("LLM stale-law migration experiment")
    if b["llm_status"] != "measured":
        pending.append("LLM review measurements for all 12 data problems")
    if b["mixed_hybrid"]["candidate_rows"] and b["mixed_hybrid"].get("model_error") and not b['mixed_hybrid'].get('model_records'):
        pending.append("Bounded hybrid LLM review evidence")
    status = {
        "status": "complete" if not pending else "external_evidence_pending",
        "pending": pending,
        "test_methods": tests.testsRun,
        "tax_fixtures": a["methods"]["hand_rules"]["case_count"],
        "description_fixtures": a["parser"]["total"],
        "nyc_rows": b["dataset_manifest"]["rows"],
        "python": sys.version,
        "platform": platform.platform(),
        "run_at_utc": datetime.now(timezone.utc).isoformat(),
        "elapsed_seconds": time.perf_counter() - started,
        "parameters": vars(args),
        "implementation_hashes": {
            str(p.relative_to(ROOT)).replace("\\", "/"): digest(p)
            for folder in ["project_a", "project_b", "common", "scripts", "tests"]
            for p in sorted((ROOT / folder).rglob("*.py"))
        },
        "fixture_hashes": {
            str(p.relative_to(ROOT)).replace("\\", "/"): digest(p)
            for p in sorted((ROOT / "project_a/tests/fixtures").glob("*.json"))
        },
        "report_hashes": {
            p: digest(ROOT / p) for p in ["RESULTS_A.md", "RESULTS_B.md", "DECISION_MATRIX.md"]
        },
    }
    write_json(ROOT / "artifacts/run_manifest.json", status)
    print(json_status(status), flush=True)
    if pending and args.require_complete:
        raise SystemExit(2)


def json_status(status):
    import json

    return json.dumps({k: status[k] for k in ["status", "pending", "elapsed_seconds"]}, indent=2)


if __name__ == "__main__":
    main()
