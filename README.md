# Rules, statistics and LLMs

Two Python experiments from the supplied Fire AI assignment. Everything is local;
no repository has been created or pushed on GitHub.

The useful starting point is [DECISION_MATRIX.md](DECISION_MATRIX.md). The full
measurements are in [RESULTS_A.md](RESULTS_A.md) and [RESULTS_B.md](RESULTS_B.md).
Read [DEFENCE.md](DEFENCE.md) alongside the code before the interview.

## Run the whole submission

Python 3.10 or newer. The offline path uses only the Python standard library:

```powershell
python reproduce.py
```

This verifies saved data/source checksums, replays independent official-calculator
observations, runs the tests, benchmarks both projects and regenerates the three
results documents and `artifacts/run_manifest.json`. Allow roughly two minutes on
this laptop. Accuracy/counts are deterministic; wall/CPU timings are measured again
and naturally change. Source acquisition and LLM calls use pinned recorded evidence
by default, so an offline rerun does not consume API quota.

The run manifest is the authoritative completion status. At the time of local
implementation, the Gemini experiments require a free-tier API key. Unmeasured
model cells are `N/A`; no rule-based stub is passed off as an LLM. All three tax
paths and all three detector families have real implementations.

## Fill the Gemini evidence

Copy `.env.example` to `.env` and set `GEMINI_API_KEY` to a Google AI Studio free-tier
key. Do not commit `.env`. The documented model/paid-price assumptions are
configurable; choose a model actually available to your account.

```powershell
python reproduce.py --live --require-complete
```

This fills missing calls, preserving actual prompts, outputs, model versions,
token metadata and latency under `artifacts/live/`. Already recorded calls are
replayed, so the command can resume across daily quota resets. The fixed Gemini comparison cohort contains 200 profiles; the deterministic regression suite contains 916. The live cohort
may exceed a free-tier day's quota. Quota/network/model failures are reported and
never replaced with fake successes. Exit code 2 means required external evidence
is still missing; exit code 1 means a failed check. Default offline reproduction
can finish with an explicit pending status and exit code 0.

For a small live connectivity experiment, `--live-limit 10` selects a smaller
tax cohort. It is a development run, not completion of the full assignment.

`artifacts/live/` is ignored by Git because service calls could contain user financial
descriptions. `python -m scripts.export_benchmark_evidence` copies only the recorded
assignment jobs to `data/experiments/gemini/` for offline reproduction, after checking
that the configured key is absent. The export uses public 311 and synthetic inputs.

## Local service

```powershell
python service.py
```

The server listens on `127.0.0.1:8000`. It offers `GET /health` and JSON POST
endpoints `/parse`, `/tax/text`, `/tax`, `/quality`. The tests exercise real local
HTTP requests, not only direct function calls.

```powershell
$body = @{ profile = @{ salary = 1200000; financial_year = '2024-25'; age = 35; resident = $true }; method = 'rules' } | ConvertTo-Json -Depth 8
Invoke-RestMethod http://127.0.0.1:8000/tax -Method Post -ContentType 'application/json' -Body $body
```

Set `method` to `compiled` for the saved LLM-authored policy candidate. `llm`
requires `allow_external_call=true` and a configured key. The endpoint is an
experiment: its arithmetic is scored as returned, not silently repaired by rules.

```powershell
$body = @{ text = 'FY 2025-26, meri salary 12.75 lpa, age 30, resident hu, koi deduction nahi.' } | ConvertTo-Json
Invoke-RestMethod http://127.0.0.1:8000/tax/text -Method Post -ContentType 'application/json' -Body $body
```

An incomplete description returns questions without a calculated answer. This
parser is deliberately conservative; use structured inputs for detailed claims.

## Structured tax input

Amounts are **annual whole rupees**, not CTC or take-home. Age is at the end of the
selected financial year. `resident` means Indian income-tax residency. Unlisted
deductions default to zero: providing a structured profile certifies that the
listed claims are complete and eligible. Plain-language users must explicitly
confirm completeness before calculation.

```json
{
  "salary": 2000000,
  "financial_year": "2024-25",
  "age": 35,
  "resident": true,
  "section_80c": 150000,
  "nps_80ccd_1b": 50000,
  "health_self": 25000,
  "health_parents": 50000,
  "family_senior": false,
  "parents_senior": true,
  "home_interest": 200000,
  "home_loan_qualifies_2l": true,
  "hra_periods": [
    { "salary_basis": 800000, "received": 300000, "rent": 360000, "metro": true }
  ]
}
```

`salary` includes HRA and its salary basis. For each HRA period use matching-period
amounts; city changes need separate periods. Metro means Delhi, Mumbai, Kolkata or
Chennai, not every city commonly called a metro. `parents_senior`/`family_senior`
certify the relevant insured person is a resident senior for section 80D. Do not
double count own NPS between 80C and additional NPS. `home_interest` includes only
the eligible annual self-occupied claim, including any eligible pre-construction
instalment. Mixed insured/uninsured group claims need member-level clarification;
the simplified input rejects them instead of guessing.

Final payable is rounded under section 288B to INR 10, while the response also
shows unrounded tax and a signed clause-linked ledger. Scope is the salary-only
assignment and its stated self-occupied-interest exception. This is not an ITR
filing system; TDS, refunds, interest, special-rate income and other income heads
are not modelled.

## Data and evidence

- `data/nyc/`: 12,000 real 2023 requests, 1,000 per month, exact queries and hashes.
  A coverage sample, not a random sample of all NYC requests.
- `data/sources/`: saved official tax material and retrieval manifest.
- `data/official_calculator/`: the actual deployed official calculator asset and
  60 recorded calculations on 30 net-income profiles. `scripts/verify_official.py`
  checks hashes and compares those results on every reproduction. This validates
  tax on net income, not independently calculated HRA/80D eligibility.
- `project_a/tests/fixtures/`: 916 frozen expected cases and 50 labelled descriptions.
- `artifacts/`: per-case and per-trial outputs behind every results table.

To re-execute the official calculator's saved JavaScript rather than replay its
recorded observations, install Node and run `node scripts/run_official.mjs`, then
`python reproduce.py`. The isolated VM runs only the extracted official calculation
functions; source hash changes require review. No browser session or credentials
are used.

To deliberately refresh public source data, run `python reproduce.py --fetch`.
The cached month files are retained unless explicitly replaced; fetching a changed
dataset is a new experiment, not the same snapshot. Review the manifest and update
baselines deliberately. The original assignment PDF is retained unchanged.

## Structure

```text
project_a/      salary model, parser, rules, query LLM, compiled policies, tests
project_b/      raw profiling, injector, reference fit, detectors, hybrid, tests
common/        JSON/hash helpers and auditable Gemini REST client
scripts/       acquisition, official validation, fixture authoring, report generation
service.py     loopback JSON API
reproduce.py   one-command checks, experiments and reports
```

There is no framework layer around arithmetic, no vector database and no model
training job. Each addition would need a concrete benefit that this assignment
does not currently demonstrate.
