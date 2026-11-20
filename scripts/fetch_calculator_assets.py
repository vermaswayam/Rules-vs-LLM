"""Fetch the calculator assets actually discovered in the official page, no guessed URLs."""

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts.fetch_sources import fetch
from common.io import ROOT, read_json, write_json, digest

if __name__ == "__main__":
    log = read_json(ROOT / "data/official_calculator/access_log.json")
    assets = []
    for page in log["probes"]:
        for url in page.get("scripts", []):
            if "/etds-income-tax-calculator/" in url or "/foservices/main." in url:
                body, final = fetch(url)
                name = "calculator.js" if "etds-income-tax-calculator" in url else "eportal_main.js"
                path = ROOT / "data/official_calculator" / name
                path.write_bytes(body)
                assets.append(
                    {
                        "path": name,
                        "url": url,
                        "final_url": final,
                        "sha256": digest(path),
                        "bytes": len(body),
                    }
                )
                print(assets[-1], flush=True)
    write_json(ROOT / "data/official_calculator/assets.json", assets)
