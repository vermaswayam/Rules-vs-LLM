# Decision matrix

Generated from the same run as the results. Decisions are limited to the observed corpus. `hybrid` means multiple explicit stages; it does not assert that Gemini has already beaten a cheaper check.

| Component / check | Choice | Measurement | Why / limitation |
|---|---|---|---|
| A: gross input + clarification gate | rule | 50/50 labelled descriptions | Narrow supported grammar; never invents an eligibility fact. |
| A: tax arithmetic / rebate / surcharge / cess / rounding | rule | 100.00% of 916 cases, 10 identical calls each; median 0.438ms | Reconciling clause ledger; official-asset net-income checks 30/30. |
| A: rule preparation | hybrid | Codex candidate 100.00% on same fixtures; Gemini compilation separately measured | Constrained policy data plus deterministic gates; authoring assistance, no runtime model. |
| A: query-time arithmetic experiment | LLM (experimental) | 200 real cases measured, status measured | No fabricated accuracy, latency or determinism; no measured reason to ship it. |
| A: yearly release gate | rule | 325 stale-policy silent failures caught; all candidate failures cleared | Pin FY, source and policy hash; test old and new years. |
| B: Schema/column contract | rule | Rule recall/proxy FAR 100.00%/0.00%; stat 100.00%/0.00% | Missing columns are a contract fact; the statistical family adds no benefit here. |
| B: Numeric type contract | rule | Rule recall/proxy FAR 100.00%/0.00%; stat 100.00%/0.00% | Reject before numeric conversion can hide a producer type change. |
| B: Timestamp format | rule | Rule recall/proxy FAR 100.00%/0.00%; stat 100.00%/0.00% | Explicit producer format; an unknown format must be versioned, not guessed. |
| B: Swapped coordinates | rule | Rule recall/proxy FAR 100.00%/0.00%; stat 100.00%/0.00% | Reverse NYC bounds give a concrete explanation; customer-specific geography is required. |
| B: Exact identity | rule | Rule recall/proxy FAR 100.00%/0.00%; stat 100.00%/0.00% | Hash/content equality needs no probabilistic judgment. |
| B: Near-duplicate candidate | rule | Rule recall/proxy FAR 100.00%/0.00%; stat 100.00%/0.08% | Normalized equality covers the measured variants; fuzzy matching adds control alerts without improving recall here. Both remain candidate warnings. |
| B: Agency descriptor-null shift | statistical | Rule recall/proxy FAR 62.50%/0.00%; stat 93.75%/0.00% | Support-aware shift catches smaller changes than fixed 10pp increase; batch window matters. |
| B: Negative lifecycle duration | rule | Rule recall/proxy FAR 100.00%/0.00%; stat 100.00%/0.00% | Chronology is an invariant; a learned lower support is unnecessary. |
| B: ZIP/borough compatibility | hybrid | Rule recall/proxy FAR 100.00%/0.00%; stat 82.64%/0.00% | Training relation produces a candidate; unresolved geography is not silently repaired. |
| B: Complaint/descriptor relation | hybrid | Rule recall/proxy FAR 100.00%/0.00%; stat 62.85%/0.08% | Use observed relations to flag candidates; new taxonomy combinations may be legitimate. |
| B: Resolution/status semantics | hybrid | Rule recall/proxy FAR 100.00%/0.00%; stat 0.00%/1.08% | Explicit phrases beat this weak token model on injection; broader semantics remain review work. |
| B: Personal data in text | hybrid | Rule recall/proxy FAR 75.52%/2.42%; stat 100.00%/2.42% | Pattern checks plus token-anomaly candidates; contextual names and public agency contacts need review. |
| B: semantic Gemini review | LLM (experimental) | measured; 12/12 problem cohorts recorded | Bound candidate rows and tokens; retain unresolved status during outages. |
| B: publication / candidate queue | hybrid | Mixed throughput 1,236 rows/s; 82 candidate rows, 0 reviewed | Hard checks block; semantic queue state stays explicit. |

See RESULTS_A.md and RESULTS_B.md for denominators, timing scope, cost assumptions and unverified requirements.
