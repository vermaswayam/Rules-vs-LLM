"""Minimal Gemini REST client with real-call evidence and explicit replay semantics.

No SDK, hidden fallback or estimated token counts. Failed/incomplete requests raise.
The key is sent in a header, never a URL or an evidence file.
"""

from datetime import datetime, timezone
import hashlib
import json
import os
import time
from threading import Lock
from urllib.error import HTTPError
from urllib.request import Request, urlopen
from .io import ROOT, read_json, write_json


def load_env():
    path = ROOT / ".env"
    if path.exists():
        for line in path.read_text(encoding="utf-8-sig").splitlines():
            if "=" in line and not line.lstrip().startswith("#"):
                key, value = line.split("=", 1)
                os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


class GeminiUnavailable(RuntimeError):
    pass


class ModelOutputError(ValueError):
    """A real response failed validation; it is a measured model failure."""

    def __init__(self, message, record):
        super().__init__(message)
        self.record = record


class Gemini:
    def __init__(self, live=False):
        load_env()
        self.model = os.getenv("GEMINI_MODEL", "gemini-3.5-flash-lite")
        self.key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
        self.live = live
        self.last_call = 0.0
        self._rate_lock = Lock()
        self.input_price = float(os.getenv("GEMINI_INPUT_USD_PER_MILLION", ".30"))
        self.output_price = float(os.getenv("GEMINI_OUTPUT_USD_PER_MILLION", "2.50"))
        self.interval = float(os.getenv("GEMINI_REQUEST_INTERVAL_SECONDS", "6"))

    def generate(self, prompt, schema, experiment, repeat=None):
        material = json.dumps([self.model, prompt, schema, repeat], sort_keys=True)
        key = hashlib.sha256(material.encode()).hexdigest()
        path = ROOT / "artifacts/live" / f"{key}.json"
        if not path.exists():
            path = ROOT / 'data/experiments/gemini' / f'{key}.json'
        if path.exists():
            result = read_json(path)
            result["replayed"] = True
            if result.get('output_error'):
                raise ModelOutputError(result['output_error'], result)
            return result
        if not self.live:
            raise GeminiUnavailable(
                "No recorded Gemini response for this experiment. Run reproduce.py --live with GEMINI_API_KEY."
            )
        path = ROOT / 'artifacts/live' / f'{key}.json'
        if not self.key:
            raise GeminiUnavailable(
                "GEMINI_API_KEY is not configured; no LLM result was simulated."
            )
        body = {
            "contents": [{"role": "user", "parts": [{"text": prompt}]}],
            "generationConfig": {
                "temperature": 0,
                "responseMimeType": "application/json",
                "responseSchema": schema,
                "maxOutputTokens": 16384,
            },
        }
        request = Request(
            f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent",
            data=json.dumps(body).encode(),
            headers={"Content-Type": "application/json", "x-goog-api-key": self.key},
            method="POST",
        )
        started, attempts = None, []
        for attempt in range(4):
            # Space request STARTS across workers. HTTP I/O does not hold the lock.
            with self._rate_lock:
                time.sleep(max(0, self.interval - (time.perf_counter() - self.last_call)))
                self.last_call = time.perf_counter()
            if started is None:
                started = time.perf_counter()
            try:
                with urlopen(request, timeout=90) as response:
                    raw = json.load(response)
                attempts.append({'http_status': 200})
                break
            except HTTPError as exc:
                attempts.append({'http_status': exc.code})
                # 5xx capacity failures can recover. A 429 is left explicit so a
                # daily free quota is not repeatedly hammered or silently upgraded.
                if exc.code in [500, 502, 503, 504] and attempt < 3:
                    time.sleep(5 * (2**attempt))
                    continue
                raise GeminiUnavailable(
                    f"Gemini HTTP {exc.code} after {attempt+1} attempt(s); no fallback was used."
                ) from None
            except OSError as exc:
                if attempt < 2:
                    time.sleep(5 * (2**attempt))
                    continue
                raise GeminiUnavailable(
                    f"Gemini connection failed ({type(exc).__name__}); no fallback was used."
                ) from None
        elapsed = time.perf_counter() - started
        candidates = raw.get("candidates", [])
        output_error = None
        if not candidates or candidates[0].get("finishReason") != "STOP":
            output_error = 'Gemini did not return a complete response'
        content = "".join(
            part.get("text", "")
            for part in (candidates[0].get("content", {}).get("parts", []) if candidates else [])
            if not part.get("thought")
        )
        try:
            parsed = json.loads(content)
        except json.JSONDecodeError:
            parsed = None
            output_error = output_error or 'Gemini returned invalid JSON'
        usage = raw.get("usageMetadata", {})
        input_tokens = usage.get("promptTokenCount", 0)
        output_tokens = usage.get("candidatesTokenCount", 0) + usage.get("thoughtsTokenCount", 0)
        result = {
            "experiment": experiment,
            "model": self.model,
            "model_version": raw.get("modelVersion"),
            "created_at": datetime.now(timezone.utc).isoformat(),
            "request_sha256": key,
            "prompt": prompt,
            "schema": schema,
            "repeat": repeat,
            "response": parsed,
            "output_error": output_error,
            "raw_response": raw,
            "latency_seconds": elapsed,
            "http_attempts": attempts,
            "usage": usage,
            "projected_paid_usd": (
                input_tokens * self.input_price + output_tokens * self.output_price
            )
            / 1e6,
            "prices_usd_per_million": {
                "input": self.input_price,
                "output_including_thinking": self.output_price,
            },
            "invoice_usd": 0,
            "invoice_assumption": "User must use a free-tier project; this client does not verify billing tier",
            "replayed": False,
        }
        write_json(path, result)
        if output_error:
            raise ModelOutputError(output_error, result)
        return result
