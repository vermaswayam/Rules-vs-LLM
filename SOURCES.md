# Sources and provenance

Only the assignment's named substantive sources were used: the Income Tax
Department/Finance Acts and NYC Open Data 311. Google documentation was consulted
for the required Gemini integration and price assumptions. No third-party tax
calculator, Kaggle copy or generated NYC dataset supplies benchmark ground truth.

## Indian salary tax

- [Income Tax Department, AY 2025-26 salaried individuals](https://www.incometax.gov.in/iec/foportal/help/individual/return-applicable-3)
- [Income Tax Department, AY 2026-27 salaried individuals](https://www.incometax.gov.in/iec/foportal/help/individual/return-applicable-1)
- [Historical section 115BAC, Finance (No.2) Act 2024 amendments](https://www.incometaxindia.gov.in/hi/w/section-115bac-5)
- [Section 115BAC with Finance Act 2025 amendments](https://www.incometaxindia.gov.in/hi/w/section-115bac-6)
- [Section 87A, historical version](https://www.incometaxindia.gov.in/w/section-87a-24)
- [Finance Act 2025 section 20, amendment of section 87A](https://www.incometaxindia.gov.in/w/section-20-111)
- [Section 288A, historical 2024 version](https://www.incometaxindia.gov.in/hi/w/section-288a-58)
- [Section 288B, historical 2024 version](https://www.incometaxindia.gov.in/hi/w/section-288b-58)
- [Section 80D](https://wmstatic-prd.incometaxindia.gov.in/hi/w/section-80d-59)
- [Section 24, housing interest](https://wm.incometaxindia.gov.in/w/section-24-64)
- [Department salary/HRA treatment](https://wm.incometaxindia.gov.in/w/treatment-of-income-from-different-sources-1)
- [Official calculator](https://www.incometaxindia.gov.in/income-tax-calculator)
- [Official calculator user manual](https://www.incometax.gov.in/iec/foportal/help/all-topics/e-filing-services/income-tax-calculator-um)

Saved pages and the Department's Finance Act 2025 highlights PDF are indexed in
`data/sources/manifest.json`. The historical statutory versions matter: today's
site also contains the later Income-tax Act 2025, which is not the requested law
for the two financial years. The old standalone 2024 Finance Act PDF link returned
404, so the corresponding historical Department statutory text was saved instead.

The official calculator page exposes its current JavaScript asset in a script
tag. Its exact URL/hash is in `data/official_calculator/assets.json`. The wrapper
uses its unchanged calculation functions and the UI's FY-specific assessment-year
selection. `check_outputs.json` holds 60 actual official-code results for 30 salary
profiles; `check_inputs.json` independently specifies each net taxable income.
Section 288B is applied to the calculator's displayed whole-rupee result before
comparing final payable. This is not described as an automated browser visit or
independent verification of the gross-to-net deduction calculation.

## NYC 311

- [NYC Open Data dataset, erm2-nwe9](https://data.cityofnewyork.us/Social-Services/311-Service-Requests-from-2020-to-Present/erm2-nwe9)
- [Official JSON API](https://data.cityofnewyork.us/resource/erm2-nwe9.json)
- [NYC description of dataset changes](https://www.nyc.gov/opendata/news/all-news/311-Service-Requests-Updates)

The public labels Complaint Type/Descriptor have changed to Problem/Problem
Detail, while the backend API names remain `complaint_type`/`descriptor`. The API
field names are used in this project. The dataset is updated daily, including
historical records. `data/nyc/manifest.json` pins the acquisition and every monthly
query, and records the population count separately from the 12,000-row sample.

## Gemini API

- [Official generateContent API reference](https://aistudio.google.com/api-reference/generate-content)
- [Official API pricing](https://aistudio.google.com/docs/pricing)

The configured default is `gemini-3.5-flash-lite`, with planning paid rates USD
0.30/million input tokens and USD 2.50/million output tokens, including thinking.
The documentation listed a free standard tier at research time. Availability and
account quotas are external state; use a model your free-tier account supports.
The client records actual model version and token metadata when called. It does
not infer invoice charges from the existence of an API key.
