# Salary-only rules: FY 2024-25 / AY 2025-26

This is an implementation-oriented paraphrase, not a substitute for the Acts.
Official source snapshots and retrieval hashes are in data/sources/manifest.json.

- Section 16(ia), amended by Finance (No.2) Act 2024 section 10: standard deduction is salary or INR 50,000, whichever is less, under old regime; INR 75,000 under section 115BAC new regime.
- Section 115BAC(1A), Finance (No.2) Act 2024: new taxable-income bands 0-300,000 at 0%; 300,000-700,000 at 5%; 700,000-1,000,000 at 10%; 1,000,000-1,200,000 at 15%; 1,200,000-1,500,000 at 20%; above 1,500,000 at 30%. Apply rates only to the portion in each band.
- First Schedule, old regime: ordinary individual 0-250,000 at 0%; 250,000-500,000 at 5%; 500,000-1,000,000 at 20%; above 1,000,000 at 30%. Resident age 60-79: initial exemption 300,000; resident age 80+: initial exemption 500,000. Nonresidents do not receive the age-based exemption.
- Section 10(13A), Rule 2A: old-regime HRA exemption per period is the nonnegative minimum of actual HRA, rent minus 10% of relevant salary, and 50% of relevant salary for Delhi/Mumbai/Kolkata/Chennai (40% elsewhere). Relevant salary is basic + qualifying retirement-benefit DA + turnover-based commission. Sum same-period exemptions. No rent means zero exemption. HRA is included in gross salary.
- Sections 80C/80CCE: up to 150,000 in aggregate eligible contributions under old regime. Input includes employee EPF. Section 80CCD(1B): up to 50,000 additional own NPS, excluding amounts already claimed under 80C/80CCD(1).
- Section 80D: old-regime self/spouse/dependent-children bucket 25,000 (50,000 where eligible resident senior); separate parents bucket 25,000 (50,000 where eligible resident senior parent). Premiums must be noncash. Preventive check-ups may be cash, with a combined 5,000 cap within the bucket limits. Eligible uninsured senior medical expenditure fits within the relevant 50,000 bucket; no simultaneous premium claim for that insured person. Do not waste a shared check-up cap on an already-full bucket. This implementation requests member-level clarification for mixed insured/uninsured groups.
- Section 24(b): old-regime self-occupied interest up to 200,000 for qualifying purchase/construction loan after 1-Apr-1999 completed within the statutory five-year period; otherwise 30,000. Section 71(3A): house-property loss set-off against salary limited to 200,000. In this salary-only scope the self-occupied interest is the sole included house-property exception.
- Section 115BAC(2): HRA, the covered Chapter VIA deductions and self-occupied interest are unavailable in the new regime. Chapter VIA deductions cannot make total income negative (sections 80A/80AB).
- Section 87A: only resident individuals. Old regime: rebate is min(tax, 12,500) at total income up to 500,000. New regime: rebate is min(tax, 25,000) at total income up to 700,000. Above 700,000, rebate marginal relief reduces tax to min(slab tax, income minus 700,000); never below zero. At 700,000 taxable income the actual slab tax is 20,000; the statutory rebate cap is still 25,000.
- Applicable First Schedule surcharge: above 5,000,000 10%; above 10,000,000 15%; above 20,000,000 25%; above 50,000,000 old regime 37%, new regime stays 25%. Marginal relief caps tax plus surcharge at the threshold tax including threshold surcharge plus the excess income. Threshold tests are strict greater-than.
- Health and Education Cess: 4% of tax after rebate plus surcharge after surcharge marginal relief.
- Sections 288A and 288B: round taxable income and final tax payable to nearest 10 rupees, half upwards. Do not round every slab or relief step to whole rupees. Show pre-rounding amounts as well as final payable.

Official references:
https://www.incometax.gov.in/iec/foportal/help/individual/return-applicable-3
https://www.incometaxindia.gov.in/w/section-87a-24
https://www.incometaxindia.gov.in/hi/w/section-115bac-5 (official historical statutory snapshot; the legacy Finance Act PDF URL returned 404)
https://www.incometaxindia.gov.in/hi/w/section-288a-58
https://www.incometaxindia.gov.in/hi/w/section-288b-58
