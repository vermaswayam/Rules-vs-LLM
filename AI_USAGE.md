# AI usage

Codex was used to read the brief, research the named official sources, author code,
prepare tests, inspect benchmark failures and write the accompanying explanations.
No other people or delegated agents worked on the assignment. No GitHub actions,
commits, remote repositories or pushes were performed.

The bundled compiled-policy candidates were written once by Codex from the legal
rule bundle, then checked by the deterministic fixture gate. They are labelled as
Codex candidates, not Gemini-generated or independently human-approved policies.
The Gemini REST client, query-time calculator, one-time compiler and batch reviewer
are implemented. Their actual execution/evidence status is recorded by reproduction;
missing API credentials do not become invented measurements.

One concrete AI mistake was in the first section 80D check-up calculation. It
allocated INR 4,000 of the combined INR 5,000 check-up cap to the family bucket even
though the INR 25,000 family premium had already filled that bucket. A parent
check-up of INR 4,000 then received only INR 1,000 of deduction. The wrong total
deduction was INR 26,000; the correct total is INR 29,000. I added
`test_checkup_cap_not_wasted_on_already_full_bucket`, observed the failure, then
changed allocation to consume the shared cap only where a bucket still has space.
The regression stays in the suite.

AI-generated expected answers are not independent official validation. The frozen
oracle uses a different calculation form from production, manual examples add
anchors, and 30 salary profiles were checked against the calculation functions
downloaded from the official Income Tax Department calculator. Raw outputs and
hashes are preserved. That independent check covers net-income arithmetic; it does
not magically validate every deduction interpretation.

The interview preparation document explains what the code does and where evidence
is incomplete. It should be used to learn and modify the implementation, not as a
claim that this work was written without AI. The assignment explicitly permits AI
and requires this note.
