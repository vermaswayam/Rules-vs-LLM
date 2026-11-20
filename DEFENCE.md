# Understanding and defending the implementation

Start by running `python reproduce.py`, reading its final status, then opening
`DECISION_MATRIX.md`. You should be able to explain the decisions and the limits,
not memorize a claim that every component is perfect.

## A five-minute walkthrough

1. Open `project_a/models.py`. Explain the difference between gross salary, CTC,
   taxable income, and final payable. Show why unknown housing-loan eligibility
   raises instead of becoming an assumed INR 2 lakh deduction.
2. Open `project_a/engine.py`. Trace one example from gross salary to deductions,
   taxable-income rounding, slabs, rebate, surcharge relief, cess and final rounding.
   Add the signed ledger entries: they must equal payable.
3. Open `project_a/policy.py` beside the two JSON policies. Only three numerical
   policy fields change for FY25 in this scope. The interpreter is shared, so don't
   claim the hand and compiled implementations are independently written algorithms.
4. Open `project_b/injector.py` and one entry in `dq_trial_results.json`. Point out
   the seed, eligible rows, requested vs actual rate, and labels kept out of the data.
5. Open `project_b/hybrid.py`. Show the difference between a hard contract failure,
   a statistical warning and an unresolved semantic candidate. Missing a model
   response must not turn an unresolved row into a clean row.

## Questions you are likely to hear

**Why not ask an LLM to compute tax?** The formula is small and discontinuous at
rebate/surcharge boundaries. We need exact arithmetic, reproducibility and a ledger.
Rules establish those properties directly. Compare the actual model results when
available; don't claim Gemini was worse when it was never run.

**Why Decimal?** Binary floating point cannot exactly represent many decimal
fractions. Thresholds and rounding matter here. Integer annual inputs plus Decimal
rates preserve exact intermediate arithmetic; sections 288A/288B specify where
rounding occurs.

**Explain the INR 12.75 lakh headline.** FY25 new regime subtracts INR 75,000
standard deduction, leaving INR 12 lakh taxable. Its slab tax is INR 60,000 and the
resident 87A rebate removes it. It does not mean INR 12.75 lakh is a universal
exemption for all income or a nonresident.

**What happens one rupee above that salary?** First apply section 288A. Gross
INR 1,275,001 gives net INR 1,200,001, rounded to INR 1,200,000, so payable is still
zero. At gross INR 1,275,010, taxable excess is INR 10. Rebate marginal relief caps
income tax at INR 10, cess makes INR 10.40, and final payable rounds to INR 10.
This is why boundary tests must account for statutory rounding, not just +/-1.

**Rebate relief versus surcharge relief?** Rebate relief limits the jump immediately
above the resident new-regime rebate threshold. Surcharge relief limits tax plus
surcharge above high-income thresholds. They have different conditions and bases;
cess comes after both.

**Can someone claim HRA and home interest together?** That is not inherently
impossible. Work location, rented accommodation and ownership facts matter. This
engine accepts independently eligible claims rather than banning the combination.
It asks for matching-period HRA inputs and housing-loan eligibility.

**How independent are your tests?** The frozen oracle uses closed-form tax bases;
production integrates slabs. Both can share a mistaken interpretation. Manual
anchors and the official deployed calculator asset supply additional evidence.
The official net-income calculator does not validate eligibility deductions.

**Is the compiled system really a different implementation?** It is a different
policy-authoring path into the same small interpreter. The model emits declarative
data once. That is safer to inspect than arbitrary model-written Python. It does
not automatically solve changes in eligibility logic outside the policy language.

**Why does a schema injector affect the whole batch?** A dropped column changes
the dataset contract. Calling that a 1% row corruption would give a misleading
denominator. Row-level and event-level metrics are both retained.

**What is the false-alarm ground truth?** The held-out real records are structurally
screened, but semantic cleanliness is not exhaustively labelled. The report calls
its control-alert rate a proxy FAR. Unknown category pairs, agency contact numbers
and missing closure dates can be legitimate. A production true FAR needs blinded
review of both alerted and unalerted examples.

**Why can the mixed batch miss a null spike?** The injector concentrates nulls in
one segment; the detector aggregates by agency over the whole mixed batch. The
effect can be diluted. That's a real limitation, retained in the results. Use
producer/agency/time windows and minimum support in production; don't conceal it
by changing labels after observing the result.

**Why can exact-duplicate statistics equal a rule?** Equality/frequency checks
collapse to the same operation for exact identity. It is reasonable for that
baseline to add no value. Statistical models earn their place on distribution
shifts and fuzzy candidates, not on every possible problem.

**Does perfect injection recall prove real-world quality?** No. Templates have
limited variety, names differ from the real world, and a model can overfit them.
Use multiple rates, variants, independent seeds, customer holdouts and adjudicated
natural errors before claiming generalization.

**What does 100,000 users tell you about capacity?** Almost nothing without request
frequency and peaks. For B, 50 million rows/day is about 579 rows/s averaged over
the day. Burst rate, state, I/O and tenant skew determine worker sizing.

## Practice making these live changes

- Change one new-regime slab boundary in a copied policy; run the fixture gate and
  show the failing cases before updating independent expectations from a source.
- Temporarily restore the FY24 rebate cap in the FY25 policy. Explain the mutation
  count in `RESULTS_A.md` and why changing only slabs is insufficient.
- Add a city alias for HRA at the input layer; preserve the legal four-city set.
- Add a new producer's accepted date format to an explicit contract version rather
  than making the parser accept every ambiguous slash date.
- Change the null-spike window or z threshold, rerun, and explain the recall/alert
  volume trade-off. Never tune against the final holdout and still call it unseen.
- Remove Gemini credentials. Show that deterministic service calculations continue
  and semantic candidates remain visibly unresolved.

## What you should state plainly

This is a tested local take-home implementation, not a certified tax-filing product
or a production multi-tenant ingestion service. There is a deliberately narrow
language parser, sampled NYC data, bounded in-batch duplicate state and a small
text baseline. The live Gemini evidence status is in the generated manifest.
Do not claim human-only authorship, unmeasured LLM superiority, or a representative
NYC census. Explaining those boundaries is stronger than trying to defend a result
the experiment did not establish.
