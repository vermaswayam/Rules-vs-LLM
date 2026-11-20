"""Local JSON service for the assignment, using only the standard library.

Run: python service.py. Bind loopback by default. This is a review/demo service;
production authentication, rate limiting and durable review queues are design work.
"""

import argparse
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from common.gemini import Gemini
from project_a.models import TaxProfile
from project_a.engine import compare
from project_a.compiled import compiled_compare
from project_a.llm_query import calculate_with_llm
from project_a.parser import parse_description

MAX_BODY = 256_000


def dispatch(path, payload):
    if path == "/parse":
        return parse_description(payload.get("text"))
    if path == "/tax/text":
        parsed = parse_description(payload.get("text"))
        if parsed["status"] != "ready":
            return parsed
        return {
            "status": "calculated",
            "parsed": parsed,
            "result": compare(TaxProfile.from_dict(parsed["fields"])),
        }
    if path == "/tax":
        profile = TaxProfile.from_dict(payload.get("profile", {}))
        method = payload.get("method", "rules")
        if method == "rules":
            return compare(profile)
        if method == "compiled":
            return compiled_compare(profile)
        if method == "llm":
            # External transmission is opt-in and clearly named by the caller.
            if payload.get("allow_external_call") is not True:
                raise ValueError(
                    "LLM calls require allow_external_call=true and a configured Gemini key"
                )
            record = calculate_with_llm(profile, Gemini(live=True))
            return {
                "result": record["response"],
                "latency_seconds": record["latency_seconds"],
                "request_sha256": record["request_sha256"],
                "replayed": record["replayed"],
            }
        raise ValueError("Unknown calculator method")
    if path == "/quality":
        from project_b.data import load_split
        from project_b.reference import Reference
        from project_b.hybrid import run_hybrid

        rows = payload.get("rows")
        if (
            not isinstance(rows, list)
            or not 1 <= len(rows) <= 5000
            or any(not isinstance(r, dict) for r in rows)
        ):
            raise ValueError("rows must be a list of 1..5000 objects in the normalized contract")
        # Do not normalize away type/schema violations at the quality boundary.
        _, train, _ = load_split()
        return run_hybrid(rows, Reference(train), review_budget=32)
    raise LookupError("Unknown endpoint")


class Handler(BaseHTTPRequestHandler):
    def _respond(self, status, value):
        body = json.dumps(value, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path == "/health":
            self._respond(200, {"status": "ok", "supported_years": ["2024-25", "2025-26"]})
        else:
            self._respond(
                404, {"error": "Use GET /health or POST /parse, /tax, /tax/text, /quality"}
            )

    def do_POST(self):
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if not 0 < length <= MAX_BODY:
                self._respond(413, {"error": "Provide a JSON body up to 256KB"})
                return
            value = json.loads(self.rfile.read(length))
            if not isinstance(value, dict):
                raise ValueError("Body must be an object")
            self._respond(200, dispatch(self.path, value))
        except LookupError as exc:
            self._respond(404, {"error": str(exc)})
        except (ValueError, TypeError, KeyError) as exc:
            self._respond(422, {"error": str(exc)})
        except RuntimeError as exc:
            self._respond(503, {"error": str(exc)})

    def log_message(self, *_):
        pass  # Do not log personal financial descriptions.


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()
    print(f"Listening on http://127.0.0.1:{args.port}; Ctrl+C to stop", flush=True)
    try:
        ThreadingHTTPServer(("127.0.0.1", args.port), Handler).serve_forever()
    except KeyboardInterrupt:
        pass
