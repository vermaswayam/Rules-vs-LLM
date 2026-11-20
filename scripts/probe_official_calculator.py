"""Record access to public official calculators; never invent validated observations."""

from datetime import datetime, timezone
import re
from pathlib import Path
import sys
from urllib.parse import urljoin

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts.fetch_sources import fetch
from common.io import ROOT, write_json, digest

URLS = [
    "https://eportal.incometax.gov.in/iec/foservices/",
    "https://www.incometaxindia.gov.in/income-tax-calculator",
    "https://wmstatic-prd.incometaxindia.gov.in/hi/income-tax-calculator",
]


if __name__ == "__main__":
    results = []
    for index, url in enumerate(URLS):
        try:
            body, final = fetch(url)
            folder = ROOT / "data/official_calculator"
            folder.mkdir(parents=True, exist_ok=True)
            path = folder / f"page_{index}.html"
            path.write_bytes(body)
            text = body.decode("utf-8", errors="replace")
            scripts = [
                urljoin(final, value)
                for value in re.findall(r"<script[^>]+src=[\"\x27]([^\"\x27]+)", text)
            ]
            results.append(
                {
                    "url": url,
                    "final_url": final,
                    "sha256": digest(path),
                    "scripts": scripts,
                    "status": "page_downloaded_not_calculator_validation",
                    "bytes": len(body),
                }
            )
        except Exception as exc:
            results.append(
                {"url": url, "status": "unavailable", "error": f"{type(exc).__name__}: {exc}"}
            )
        print(results[-1], flush=True)
        write_json(
            ROOT / "data/official_calculator/access_log.json",
            {
                "retrieved_at": datetime.now(timezone.utc).isoformat(),
                "probes": results,
                "browser_attempt": "CUA native pipe unavailable (os error 2); no interactive calculator results obtained",
            },
        )
